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

### 7. Download Image Data
- **Description**: Allows users to download Docker image data in a ZIP file. This includes image history and other relevant information.
- **Use Case**: Facilitates offline analysis and record-keeping by providing a portable version of the image data.

### 8. Inspect Image Metadata
- **Description**: Shows detailed metadata of a Docker image, including labels, configuration settings, and other relevant properties.
- **Use Case**: Useful for auditing and verifying image configurations, ensuring compliance with standards and best practices.

### 9. Dockerfile Snippets
- **Description**: Retrieves and displays snippets of the Dockerfile used to build the Docker image. This provides insights into the build instructions and configurations.
- **Use Case**: Helps users understand how the image was constructed, which is valuable for documentation, reproducibility, and educational purposes.

### 10. Volume and Network Information
- **Description**: Displays information about volumes and networks associated with a Docker image. This includes details about data volumes and network configurations.
- **Use Case**: Useful for understanding resource allocations and network setups associated with Docker images, which can impact performance and connectivity.

## Useage
1. Clone the Repository
2. Install requirements (pip install requirements.txt)
3. Run (python app.py)

