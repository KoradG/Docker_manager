import subprocess
import sys


def detect_terminal():
    terminals = ["gnome-terminal", "xterm", "konsole", "lxterminal", "mate-terminal", "terminator"]
    for terminal in terminals:
        if subprocess.call(f"type {terminal}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0:
            return terminal
    return None

# Detect the terminal emulator
terminal_emulator = detect_terminal()

if not terminal_emulator:
    print("No supported terminal emulator found. Please install one of the following: gnome-terminal, xterm, konsole, lxterminal, mate-terminal, terminator.", flush=True)
    sys.exit(1)

def open_terminal_with_command(command):
    try:
        subprocess.Popen(f"{terminal_emulator} -e {command}", shell=True)
    except Exception as e:
        print(f"Error occurred while opening terminal: {e}", flush=True)


