# Docker Manager Application

## Overview

The Docker Manager is a desktop application developed to facilitate Docker container management through a user-friendly graphical interface. By leveraging PyQt5 for the GUI and Docker's Python SDK for backend operations, the application provides a streamlined approach to handling Docker environments. This tool simplifies Docker management by abstracting complex command-line operations into a graphical interface, making it accessible to users of varying expertise.
Users can start, stop and pause running containers from the main window. The collumn on the left side of the screen allows users to see which containers are runnig or stopped. Below the containers there is a section for the existing images, this area is only informative.
Users can find two buttons on the bottom right, one for a help pop-up, and one for detailing existing images. [see below](#docker-image-detailer)


## How to use

### This application only works on linux systems!
- **install** [Dependencies](#Dependencies)
- **install** pip packages `pip install requirements.txt`
- **run** `python main.py`
- In a perfect world that is how it should work...
- 
- Install and enable docker!
# With arch based systems:

- sudo pacman -S python-pyyaml
- sudo pacman -S python-docker
- sudo pacman -S python-flask
- sudo pacman -S python-numpy
- sudo pacman -S python-pyqtgraph
- sudo pacman -S python-plotly
- Run as `sudo python main.py` 
# With debian base systems:
I believe same as with arch, only apt install instead of pacman -S. 

# Other distros:
I don't know. I use arch BTW.

Run as sudo otherwise it gives segmentation fault. 
CURRENTLY TRYING TO FIX IT

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


# Docker Image Detailer

## Overview
This is a web-based tool designed to provide in-depth insights into Docker images. This application allows users to retrieve, analyze, and visualize various aspects of Docker images through a web interface. It is particularly useful for developers, DevOps engineers, and system administrators who need to understand the structure, configuration, and history of Docker images used in their projects.

## Features

### 1. View Image History
- **Description**: This feature displays the detailed history of a Docker image, including the commands used to create each layer, the size of each layer, and the date when each layer was created.
- **Use Case**: Helps users trace the origins of an image, understand the changes made over time, and troubleshoot issues related to image creation.

### 2. Image Size Breakdown
- **Description**: Provides a detailed breakdown of the sizes of each layer within a Docker image. Users can see how the size of the image is distributed across its layers.
- **Use Case**: Useful for optimizing Docker images by identifying large layers and understanding the impact of each layer on the overall image size.

### 3. Environment Variables
- **Description**: Lists all environment variables configured in a Docker image. This includes variables set during the build process or specified in the Dockerfile.
- **Use Case**: Allows users to review and verify environment settings, which can be critical for debugging application behavior or ensuring proper configuration.

### 4. Layer Comparison
- **Description**: Compares the layers of two Docker images side by side. This feature highlights differences in layer commands, sizes, and creation times.
- **Use Case**: Ideal for comparing different versions of an image to understand changes and improvements, or to identify discrepancies between similar images.

### 5. Interactive Visualizations
- **Description**: Generates interactive charts and graphs to visualize the sizes of layers in a Docker image. Users can interact with these visualizations to better understand the data.
- **Use Case**: Provides a visual representation of image sizes, making it easier to grasp complex data and identify trends or anomalies.

### 6. Logs and Build Info
- **Description**: Retrieves and displays logs related to the Docker image build process. This includes build commands, timestamps, and any relevant output.
- **Use Case**: Helps in diagnosing build issues and understanding the build process, which is useful for troubleshooting and verifying the build steps.

### 7. Inspect Image Metadata
- **Description**: Shows detailed metadata of a Docker image, including labels, configuration settings, and other relevant properties.
- **Use Case**: Useful for auditing and verifying image configurations, ensuring compliance with standards and best practices.

### 8. Dockerfile Snippets
- **Description**: Retrieves and displays snippets of the Dockerfile used to build the Docker image. This provides insights into the build instructions and configurations.
- **Use Case**: Helps users understand how the image was constructed, which is valuable for documentation, reproducibility, and educational purposes.

### 9. Volume and Network Information
- **Description**: Displays information about volumes and networks associated with a Docker image. This includes details about data volumes and network configurations.
- **Use Case**: Useful for understanding resource allocations and network setups associated with Docker images, which can impact performance and connectivity.

### 10. Image Vulnerabilities
- **Description**: Identifies and displays vulnerabilities present in a Docker image. This feature uses vulnerability databases to provide information on security issues related to the image’s components.
- **Use Case**: Essential for security auditing and ensuring that Docker images do not contain known vulnerabilities that could compromise the system.



### Dependencies

- **PyQt5**: Framework for building the graphical user interface.
- **docker**: Python SDK for interacting with Docker.
- **subprocess**: For running Docker Compose commands and handling subprocesses.
- **logging**: For application logging and error tracking.
- **trivy**: For vulnerability check


### Conclusion

The Docker Manager provides a powerful and intuitive solution for managing Docker containers and resources. By integrating PyQt5 for the graphical interface and Docker's Python SDK for backend operations, the application simplifies Docker management tasks and enhances user experience. Features such as real-time resource monitoring, container and image management, and Docker Compose deployment make it a comprehensive tool for Docker users.





