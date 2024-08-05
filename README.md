# Docker Management GUI

## Overview

The Docker Management GUI is a comprehensive desktop application aimed at simplifying Docker container management for both novice and experienced users. Leveraging the power of PyQt5 for the user interface and Docker's Python SDK for seamless backend interactions, this application provides an intuitive, graphical approach to managing Docker environments. It is designed to eliminate the complexities associated with command-line operations, making Docker management accessible to a broader audience.

With this tool, users can effortlessly list, create, start, stop, and remove Docker containers, as well as monitor their resource usage in real-time. The application also supports advanced functionalities like viewing container logs, deploying multi-container applications using Docker Compose files, and managing Docker images, networks, and volumes with ease. By visualizing key metrics and providing one-click access to essential operations, the Docker Management GUI enhances productivity and streamlines the workflow for Docker users.

## Features

### Containers Management
- **List Containers**: Displays all Docker containers with detailed information including ID, name, status, and available actions.
- **Lifecycle Management**: Start, stop, pause, unpause, and remove containers directly from the GUI.
- **Logs Viewing**: Access real-time logs for selected containers in a new terminal window for easy monitoring.
- **Resource Monitoring**: Visualize CPU, memory, and disk usage for each running container with dynamic real-time graphs.
- **Detailed Inspection**: Inspect container details and statistics.

### Images Management
- **List Images**: View a comprehensive list of Docker images with relevant details.
- **Image Operations**: Remove, tag, push, and pull images using the intuitive interface.

### Networks Management
- **List Networks**: Display all Docker networks with their properties.
- **Network Operations**: Create, inspect, and remove Docker networks seamlessly.

### Volumes Management
- **List Volumes**: View and manage Docker volumes.
- **Volume Operations**: Create, inspect, and remove volumes with a few clicks.
- **Prune Volumes**: Easily prune unused volumes to free up space.

### Docker Compose Deployment
- **Deploy Compose Files**: Deploy Docker Compose files to set up and manage multi-container applications effortlessly.


