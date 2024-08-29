# Docker Manager Application

## Overview

The Docker Manager is a desktop application developed to facilitate Docker container management through a user-friendly graphical interface. By leveraging PyQt5 for the GUI and Docker's Python SDK for backend operations, the application provides a streamlined approach to handling Docker environments. This tool simplifies Docker management by abstracting complex command-line operations into a graphical interface, making it accessible to users of varying expertise.

Run the application with `main.py`.

### Key Objectives

The application aims to:
- Provide an intuitive graphical interface for managing Docker containers, images, networks, and volumes.
- Enable real-time monitoring and management of Docker resources.
- Simplify deployment of multi-container applications using Docker Compose.
- Enhance user productivity by offering an easy-to-use alternative to command-line Docker management.

### Core Components

#### 1. DockerClient

The `DockerClient` class is the central component responsible for interacting with Docker's API through Docker's Python SDK. It abstracts the complexity of Docker API calls, offering a simplified and consistent interface for various Docker operations.

- **Initialization**:
    - Establishes a connection to the Docker engine using Docker's Python SDK.
    - Configures the Docker client for API interactions.

- **Container Operations**:
    - **List Containers**: Retrieves and returns a list of all Docker containers, including their IDs, names, statuses, and available actions.
    - **Start Container**: Starts a specified stopped container.
    - **Stop Container**: Stops a currently running container.
    - **Remove Container**: Deletes a specified container from the Docker engine.
    - **Inspect Container**: Provides detailed information about a specific container, including its configuration and status.

- **Image Operations**:
    - **List Images**: Lists all Docker images available locally with details.
    - **Pull Image**: Downloads an image from a Docker registry to the local machine.
    - **Push Image**: Uploads a local image to a Docker registry.
    - **Tag Image**: Assigns a new tag to an existing image.
    - **Remove Image**: Deletes a specified image from the local Docker repository.

- **Network Operations**:
    - **List Networks**: Retrieves a list of all Docker networks.
    - **Create Network**: Creates a new Docker network with specified parameters.
    - **Inspect Network**: Provides details about a particular network.
    - **Remove Network**: Deletes a specified Docker network.

- **Volume Operations**:
    - **List Volumes**: Displays a list of all Docker volumes.
    - **Create Volume**: Creates a new volume for Docker containers.
    - **Inspect Volume**: Provides detailed information about a specific volume.
    - **Remove Volume**: Deletes a specified Docker volume.
    - **Prune Volumes**: Removes unused volumes to free up disk space.

- **Error Handling**:
    - **Exception Management**: Handles and logs exceptions that occur during Docker API interactions.
    - **Logging**: Captures and stores error messages for troubleshooting and debugging purposes.

#### 2. ResourceMonitor

The `ResourceMonitor` class is responsible for monitoring and visualizing the resource usage of Docker containers. It collects and provides real-time data on CPU, memory, and disk usage.

- **Initialization**:
    - Sets up monitoring for the specified Docker containers.

- **Data Collection**:
    - **CPU Usage**: Retrieves and reports the CPU usage of monitored containers.
    - **Memory Usage**: Tracks and displays memory consumption.
    - **Disk Usage**: Monitors disk space usage for each container.

- **Visualization**:
    - **Real-Time Graphs**: Displays dynamic graphs representing the real-time resource usage of containers.


#### 3. GUI Components

The GUI components are implemented using PyQt5 and provide the user interface for interacting with Docker and managing Docker resources.

- **MainWindow**:
    - **Overview**: The primary application window that hosts the various interface panels and controls.
    - **Navigation**: Includes tabs or menus for accessing different management views (containers, images, networks, volumes).

- **ContainerView**:
    - **Listing**: Displays all Docker containers with detailed information.
    - **Operations**: Allows users to start, stop, remove, and inspect containers.
    - **Logs**: Provides access to real-time logs for selected containers.

- **ImageView**:
    - **Listing**: Shows a list of Docker images with relevant details.
    - **Operations**: Supports image management tasks such as removal, tagging, pulling, and pushing.

- **NetworkView**:
    - **Listing**: Displays all Docker networks and their properties.
    - **Operations**: Facilitates network creation, inspection, and removal.

- **VolumeView**:
    - **Listing**: Lists Docker volumes and their details.
    - **Operations**: Allows for volume creation, inspection, removal, and pruning.

### Application Workflow

1. **Startup**:
    - The application initializes by setting up the GUI components and backend services.
    - It loads initial data and prepares the main application window.

2. **User Interaction**:
    - Users interact with the GUI to perform Docker operations, such as managing containers or deploying applications.

3. **Backend Processing**:
    - Backend services like `DockerClient`, `DockerGui` and `ResourceMonitor` process the user's requests by interacting with Docker's API.

4. **Data Display**:
    - Results from backend operations are processed and displayed in the GUI components for user interaction.

### Dependencies

- **PyQt5**: Framework for building the graphical user interface.
- **docker**: Python SDK for interacting with Docker.
- **subprocess**: For running Docker Compose commands and handling subprocesses.
- **logging**: For application logging and error tracking.

### Conclusion

The Docker Manager provides a powerful and intuitive solution for managing Docker containers and resources. By integrating PyQt5 for the graphical interface and Docker's Python SDK for backend operations, the application simplifies Docker management tasks and enhances user experience. Features such as real-time resource monitoring, container and image management, and Docker Compose deployment make it a comprehensive tool for Docker users.

