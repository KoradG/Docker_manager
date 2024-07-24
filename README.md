# Docker Management GUI
## Overview
The Docker Management GUI is a desktop application designed to simplify Docker container management through a user-friendly graphical interface. It leverages PyQt5 for the UI and Docker's
Python SDK to interact with Docker containers, making it easy for users to manage their Docker environment without needing to use the command line.

## Features
List Containers: Displays a table of all Docker containers, showing their ID, name, status, and options for management.
Start/Stop/Remove Containers: Provides buttons to control the lifecycle of each container directly from the GUI.
View Logs: Opens a new terminal window to display real-time logs for a selected container, allowing users to monitor container output.
Monitor Resource Usage: Tracks and visualizes CPU, memory, and disk usage for each running container with real-time graphs.
List Containers: Click the "List Containers" button to view all containers along with their IDs, names, and statuses.
Container Management: Use the "Start", "Stop", and "Remove" buttons next to each container to manage its state.
View Logs: Click the "Shell" button to open a terminal that displays the container's logs in real-time.
Monitor Resources: Click the "Monitor" button to open a dedicated window with real-time graphs showing CPU, memory, and disk usage of the selected container.
