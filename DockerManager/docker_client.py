# docker_client.py
import os
import platform
import shutil
import subprocess

import docker

from logs import Logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_docker_socket_volume():
    if platform.system() == "Windows":
        return {'//./pipe/docker_engine': {'bind': '//./pipe/docker_engine', 'mode': 'rw'}}
    return {'/var/run/docker.sock': {'bind': '/var/run/docker.sock', 'mode': 'rw'}}


def _is_podman_docker_shim() -> bool:
    """
    Returns True if the 'docker' binary is actually the podman-docker shim.

    The shim is a shell script that calls Podman – unreliable for compose
    (causes 'Yunix protocol' errors on Arch Linux at runtime).
    Detected in three ways:
    1. The docker binary is a shell script (not an ELF binary)
    2. 'docker info' output contains 'podman'
    3. /usr/bin/docker contains the word 'podman'
    """
    docker_path = shutil.which("docker")
    if not docker_path:
        return False
    # Shell script check – ELF binaries start with the magic bytes \x7fELF
    try:
        with open(docker_path, "rb") as f:
            magic = f.read(4)
        if magic != b"\x7fELF":
            return True   # script → shim
    except OSError:
        pass
    # docker info based check
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=5
        )
        if "podman" in result.stdout.lower():
            return True
    except Exception:
        pass
    return False


def get_compose_command() -> list[str]:
    """
    Find the best available compose command.

    Order of preference:
    1. docker compose  – only if using real Docker (not the Podman shim)
    2. podman compose  – if the podman binary is available
    3. podman-compose  – standalone Python tool
    4. docker-compose  – legacy v1
    5. Fallback: docker compose

    The podman-docker shim (Arch Linux) is filtered out – it causes
    'Yunix protocol' errors at compose runtime, so it is skipped.
    """
    # 1. Real docker compose – shim filtered out
    if not _is_podman_docker_shim():
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, check=True, timeout=5
            )
            if b"podman" not in result.stdout.lower():
                return ["docker", "compose"]
        except Exception:
            pass

    # 2. podman compose (built-in podman subcommand)
    if shutil.which("podman"):
        try:
            subprocess.run(
                ["podman", "compose", "version"],
                capture_output=True, check=True, timeout=5
            )
            return ["podman", "compose"]
        except Exception:
            pass

    # 3. podman-compose (standalone)
    if shutil.which("podman-compose"):
        return ["podman-compose"]

    # 4. Legacy docker-compose v1
    if shutil.which("docker-compose"):
        return ["docker-compose"]

    # 5. Fallback
    return ["docker", "compose"]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class DockerClientError(Exception):
    """Custom exception for DockerClient errors."""
    pass


# ---------------------------------------------------------------------------
# DockerClient
# ---------------------------------------------------------------------------

class DockerClient:

    # Decorator defined as staticmethod so it does not receive self as first arg
    @staticmethod
    def handle_docker_api_error(func):
        """Decorator to handle Docker API errors."""
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except docker.errors.APIError as e:
                # Use self.logs.log_error (not self.log_error)
                self.logs.log_error(f"Error in {func.__name__}: {e}")
                raise DockerClientError(f"Error in {func.__name__}.") from e
        return wrapper

    def __init__(self):
        # Create Logger first so it is available even if the connection fails
        self.logs = Logger()
        try:
            self.client = docker.from_env()
        except Exception as e:
            self.logs.log_error(f"Error connecting to Docker daemon: {e}")
            raise DockerClientError("Unable to connect to Docker daemon.") from e

    def list_containers(self, all=True):
        return self.client.containers.list(all=all)

    @handle_docker_api_error
    def create_image_from_dockerfile(self, dockerfile_path, tag):
        if not os.path.isdir(dockerfile_path):
            raise ValueError(f"{dockerfile_path} is not a valid directory.")
        try:
            image, build_logs = self.client.images.build(path=dockerfile_path, tag=tag, rm=True)
            for log in build_logs:
                if 'stream' in log:
                    print(log['stream'], end='', flush=True)
            # log_info does not accept a flush kwarg
            self.logs.log_info(f"Image built from Dockerfile and tagged as {tag}.")
            return image
        except ValueError as e:
            self.logs.log_error(f"Invalid Dockerfile path: {e}")
            raise
        except docker.errors.BuildError as e:
            self.logs.log_error(f"Error building image from Dockerfile: {e}")
            raise DockerClientError("Error building image from Dockerfile.") from e
        except docker.errors.APIError as e:
            self.logs.log_error(f"API Error while building image: {e}")
            raise DockerClientError("API Error while building image.") from e

    @handle_docker_api_error
    def create_container(self, image_name, command=None, env_vars=None,
                         ports=None, volumes=None, network=None, extra_params=None):
        container = self.client.containers.create(
            image=image_name,
            command=command,
            environment=env_vars,
            ports=ports,
            volumes=volumes,
            network=network,
            detach=True,
            **(extra_params or {})
        )
        print(f"Container created with image {image_name}.", flush=True)
        return container

    @handle_docker_api_error
    def perform_container_action(self, container, action_func, action_name):
        action_func()
        updated_container = self.client.containers.get(container.id)
        print(f"Container {container.name} {action_name} successfully.", flush=True)
        return updated_container

    @handle_docker_api_error
    def start_container(self, container):
        return self.perform_container_action(container, container.start, "started")

    @handle_docker_api_error
    def stop_container(self, container):
        return self.perform_container_action(container, container.stop, "stopped")

    @handle_docker_api_error
    def pause_container(self, container):
        return self.perform_container_action(container, container.pause, "paused")

    @handle_docker_api_error
    def unpause_container(self, container):
        return self.perform_container_action(container, container.unpause, "unpaused")

    @handle_docker_api_error
    def restart_container(self, container):
        return self.perform_container_action(container, container.restart, "restarted")

    @handle_docker_api_error
    def remove_container(self, container):
        container.remove(v=True, force=True)
        print(f"Container {container.name} removed successfully.", flush=True)

    @handle_docker_api_error
    def inspect_container(self, container):
        return container.attrs

    @handle_docker_api_error
    def container_stats(self, container):
        return self.client.containers.get(container.id).stats(stream=False)

    # ── Image Management ───────────────────────────────────────────────────

    @handle_docker_api_error
    def list_images(self):
        images = self.client.images.list()
        return [{"id": img.id, "tags": img.tags if img.tags else []} for img in images]

    @handle_docker_api_error
    def remove_image(self, image_id):
        self.client.images.remove(image_id, force=True)
        print(f"Image {image_id} removed successfully.", flush=True)

    @handle_docker_api_error
    def tag_image(self, image_id, new_tag):
        image = self.client.images.get(image_id)
        image.tag(new_tag)
        print(f"Image {image_id} tagged with {new_tag}.", flush=True)

    @handle_docker_api_error
    def push_image(self, image_tag, username, password):
        self.client.images.push(
            image_tag, auth_config={'username': username, 'password': password}
        )
        print(f"Image {image_tag} pushed successfully.", flush=True)

    @handle_docker_api_error
    def pull_image(self, image_name):
        self.client.images.pull(image_name)
        print(f"Image {image_name} pulled successfully.", flush=True)

    # ── Network Management ─────────────────────────────────────────────────

    @handle_docker_api_error
    def list_networks(self):
        return self.client.networks.list()

    @handle_docker_api_error
    def remove_network(self, network_id):
        self.client.networks.get(network_id).remove()
        print(f"Network {network_id} removed successfully.", flush=True)

    @handle_docker_api_error
    def inspect_network(self, network_id):
        if isinstance(network_id, str):
            return self.client.networks.get(network_id).attrs
        raise ValueError("Expected network_id to be a string")

    @handle_docker_api_error
    def create_network(self, network_name, driver=None, options=None):
        self.client.networks.create(name=network_name, driver=driver, **(options or {}))
        print(f"Network {network_name} created successfully.", flush=True)

    # ── Volume Management ──────────────────────────────────────────────────

    @handle_docker_api_error
    def list_volumes(self):
        volumes = self.client.volumes.list()
        return [
            {
                "name": volume.name,
                "driver": volume.attrs['Driver'],
                "mountpoint": volume.attrs['Mountpoint'],
            }
            for volume in volumes
        ]

    @handle_docker_api_error
    def create_volume(self, volume_name, driver=None, **options):
        self.client.volumes.create(name=volume_name, driver=driver, **options)
        print(f"Volume {volume_name} created successfully.", flush=True)

    @handle_docker_api_error
    def inspect_volume(self, volume_name):
        return self.client.volumes.get(volume_name).attrs

    @handle_docker_api_error
    def remove_volume(self, volume_name):
        self.client.volumes.get(volume_name).remove()
        print(f"Volume {volume_name} removed successfully.", flush=True)

    @handle_docker_api_error
    def prune_volumes(self):
        self.client.volumes.prune()
        print("Volumes pruned successfully.", flush=True)


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def get_docker_client() -> DockerClient:
    """Return a fresh DockerClient instance connected to the local Docker daemon."""
    return DockerClient()


def get_podman_client():
    """
    Visszaad egy (docker.DockerClient, PodmanCapabilities) tuple-t
    a helyi Podman sockethez csatlakozva.

    The actual implementation lives in podman_utils so that
    docker_client.py does not have a hard dependency on it (optional backend).
    """
    from podman_utils import get_podman_client as _get_podman_client
    return _get_podman_client()