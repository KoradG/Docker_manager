# terminal_utils.py
import subprocess
import sys
import platform
import shutil


def detect_terminal():
    """Detect an available terminal emulator on Linux."""
    terminals = [
        "gnome-terminal",
        "xterm",
        "konsole",
        "lxterminal",
        "mate-terminal",
        "terminator",
        "xfce4-terminal",
        "tilix",
    ]
    for terminal in terminals:
        if shutil.which(terminal):
            return terminal
    return None


def open_terminal_with_command(command):
    """
    Open a terminal and run the given command.
    Works on Windows, macOS, and Linux.
    """
    system = platform.system()
    try:
        if system == "Windows":
            # Use Windows Terminal if available, fall back to cmd
            if shutil.which("wt"):
                subprocess.Popen(["wt", "cmd", "/k", command])
            else:
                subprocess.Popen(f'start cmd /k "{command}"', shell=True)

        elif system == "Darwin":  # macOS
            apple_script = f'tell application "Terminal" to do script "{command}"'
            subprocess.Popen(["osascript", "-e", apple_script])

        else:  # Linux
            terminal = detect_terminal()
            if not terminal:
                print(
                    "No supported terminal emulator found. "
                    "Please install one of: gnome-terminal, xterm, konsole, "
                    "lxterminal, mate-terminal, terminator, xfce4-terminal, tilix.",
                    flush=True,
                )
                return
            # Different terminals use different flags to run a command
            if terminal in ("gnome-terminal", "mate-terminal", "tilix"):
                subprocess.Popen([terminal, "--", "bash", "-c", command])
            elif terminal in ("xfce4-terminal",):
                subprocess.Popen([terminal, "-e", f"bash -c '{command}'"])
            else:
                subprocess.Popen([terminal, "-e", command])

    except Exception as e:
        print(f"Error occurred while opening terminal: {e}", flush=True)


# Expose a terminal_emulator value for legacy imports (may be None on Windows/macOS)
terminal_emulator = detect_terminal() if platform.system() == "Linux" else platform.system()