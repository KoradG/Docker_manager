# podman_utils.py
"""
Podman-specific helper utilities.

Podman exposes a Docker-compatible REST API, so the docker-py SDK can be
used directly – only the socket path differs.
"""

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional

import docker


# ---------------------------------------------------------------------------
# Capability flags
# ---------------------------------------------------------------------------

@dataclass
class PodmanCapabilities:
    """
    Indicates which Docker features the current Podman installation
    supports. Values are populated after connecting by calling detect().
    """
    swarm_supported: bool = False       # Podman does not support Swarm
    pause_supported: bool = True        # requires cgroups v2
    build_supported: bool = True        # podman build is available
    compose_supported: bool = False     # requires podman-compose or docker-compose

    # Version – populated after connection
    server_version: str = "unknown"
    api_version: str = "unknown"

    def detect(self, client: docker.DockerClient) -> None:
        """Query actual capabilities from the live client."""
        try:
            info = client.info()
            self.server_version = info.get("ServerVersion", "unknown")

            ver = client.version()
            self.api_version = ver.get("ApiVersion", "unknown")

            # cgroups v2 check (pause only works reliably with cgroups v2)
            cgroup_ver = info.get("CgroupVersion", "1")
            self.pause_supported = str(cgroup_ver) == "2"

            # check if podman-compose or docker-compose is available
            self.compose_supported = bool(
                shutil.which("podman-compose") or shutil.which("docker-compose")
            )
        except Exception:
            pass  # not fatal – default values are conservative

    def warnings(self) -> list[str]:
        """Return a list of known limitations for this Podman installation."""
        msgs = []
        if not self.swarm_supported:
            msgs.append("Docker Swarm is not supported under Podman.")
        if not self.pause_supported:
            msgs.append(
                "Pause/Unpause only works with cgroups v2. "
                "Check: /sys/fs/cgroup/cgroup.controllers"
            )
        if not self.compose_supported:
            msgs.append(
                "Compose not available. "
                "Install: pip install podman-compose"
            )
        return msgs


# ---------------------------------------------------------------------------
# Socket detection
# ---------------------------------------------------------------------------

def _candidate_sockets() -> list[str]:
    """
    Return candidate Podman socket paths in priority order for the current platform.
    """
    system = platform.system()

    if system == "Windows":
        return [
            "npipe:////./pipe/podman-machine-default",
        ]

    if system == "Darwin":
        home = os.path.expanduser("~")
        candidates = [
            # podman machine (QEMU / applehv)
            f"{home}/.local/share/containers/podman/machine/qemu/podman.sock",
            f"{home}/.local/share/containers/podman/machine/applehv/podman.sock",
            # podman 5.x unified path
            f"{home}/.local/share/containers/podman/machine/podman.sock",
        ]
        # also try reading from podman machine inspect output
        machine_sock = _podman_machine_socket()
        if machine_sock:
            candidates.insert(0, machine_sock)
        return [f"unix://{s}" for s in candidates]

    # Linux – rootless first, then rootful
    uid = os.getuid()
    candidates = [
        f"/run/user/{uid}/podman/podman.sock",    # XDG_RUNTIME_DIR
        "/run/podman/podman.sock",                 # rootful
        f"/tmp/podman-run-{uid}/podman/podman.sock",
    ]
    # XDG_RUNTIME_DIR override
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        candidates.insert(0, f"{xdg}/podman/podman.sock")

    return [f"unix://{s}" for s in candidates]


def _podman_machine_socket() -> Optional[str]:
    """
    Read the socket path from `podman machine inspect` output on macOS.
    Returns None if unsuccessful.
    """
    try:
        import json
        result = subprocess.run(
            ["podman", "machine", "inspect"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # Path of the first machine's socket
            if isinstance(data, list) and data:
                return data[0].get("ConnectionInfo", {}).get("PodmanSocket", {}).get("Path")
    except Exception:
        pass
    return None


def detect_podman_socket() -> Optional[str]:
    """
    Try candidate socket paths and return the first one that the current
    user has both read and write access to.

    Note: file *existence* alone is not sufficient – the rootful socket
    (/run/podman/podman.sock) is inaccessible without root even if visible.
    """
    if platform.system() == "Windows":
        return _candidate_sockets()[0]

    accessible = []
    inaccessible = []

    for sock in _candidate_sockets():
        path = sock.replace("unix://", "")
        if not os.path.exists(path):
            continue
        if os.access(path, os.R_OK | os.W_OK):
            accessible.append(sock)
        else:
            inaccessible.append(sock)

    if accessible:
        return accessible[0]

    # Socket exists but we lack permissions → return it anyway so
    # get_podman_client() can produce a precise error message
    if inaccessible:
        return inaccessible[0]

    return None


def _socket_permission_hint(path: str) -> str:
    """Short usage hint for PermissionError cases."""
    uid = os.getuid() if platform.system() != "Windows" else 0

    if f"run/user/{uid}" in path or f"podman-run-{uid}" in path:
        # Rootless socket – the daemon is probably not running
        return (
            f"Rootless Podman socket not accessible: {path}\n"
            "\n"
            "  Start the socket:\n"
            "    systemctl --user start podman.socket\n"
            "\n"
            "  Enable permanently:\n"
            "    systemctl --user enable --now podman.socket\n"
            "\n"
            "  If loginctl lingering is not enabled:\n"
            "    sudo loginctl enable-linger $USER"
        )

    # Rootful socket – /run/podman/podman.sock
    return (
        f"Rootful Podman socket requires root: {path}\n"
        "\n"
        "  Recommended – start the rootless socket:\n"
        "    systemctl --user start podman.socket\n"
        "\n"
        "  Alternative – temporary permission (until reboot):\n"
        "    sudo chmod o+rw /run/podman/podman.sock\n"
        "\n"
        "  Alternative – via ACL:\n"
        "    sudo setfacl -m u:$(whoami):rw /run/podman/podman.sock"
    )


def is_podman_available() -> bool:
    """Return True if the `podman` binary is found in PATH."""
    return shutil.which("podman") is not None


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def get_podman_client() -> tuple[docker.DockerClient, PodmanCapabilities]:
    """
    Create a docker-py client connected to the Podman socket and
    probe its capabilities.

    Returns
    -------
    (client, capabilities)

    Raises
    ------
    ConnectionError  – if no socket is accessible or permissions are insufficient
    """
    sock = detect_podman_socket()
    if sock is None:
        raise ConnectionError(
            "Podman socket not found. Make sure the Podman daemon is running:\n"
            "  Linux:  systemctl --user start podman.socket\n"
            "  macOS:  podman machine start\n"
            "  Win:    podman machine start"
        )

    path = sock.replace("unix://", "")

    # Pre-check permissions to produce a clear error message
    if platform.system() != "Windows" and os.path.exists(path):
        if not os.access(path, os.R_OK | os.W_OK):
            raise ConnectionError(_socket_permission_hint(path))

    client = docker.DockerClient(base_url=sock, timeout=10)

    # Quick ping to verify the socket actually responds
    try:
        client.ping()
    except PermissionError as exc:
        raise ConnectionError(_socket_permission_hint(path)) from exc
    except Exception as exc:
        # A docker-py a PermissionError-t sokszor egy ConnectionError-ba
        # csomagolja – kibontjuk
        cause = exc.__cause__ or exc.__context__
        if isinstance(cause, PermissionError) or "PermissionError" in str(exc):
            raise ConnectionError(_socket_permission_hint(path)) from exc
        raise ConnectionError(
            f"Podman socket found ({sock}) but not responding: {exc}"
        ) from exc

    caps = PodmanCapabilities()
    caps.detect(client)
    return client, caps