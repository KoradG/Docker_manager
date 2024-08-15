import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout, 
    QLineEdit, QLabel, QDialog, QFileDialog, QMessageBox, QVBoxLayout, QHBoxLayout, QBoxLayout,
     QWidget, QVBoxLayout, QPushButton, QTextEdit, QGridLayout
)

from PyQt5.QtCore import QThread, pyqtSignal
import os
import yaml
import subprocess
import tempfile

import docker
from docker.errors import APIError as DockerAPIError

from docker_client import get_docker_client
from resource_monitor import ResourceGraphWidget, ResourceMonitorThread
from terminal_utils import terminal_emulator, open_terminal_with_command



logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class DockerGui(QWidget):
    def __init__(self):
        super().__init__()
        self.docker_client = docker.from_env() 

            
        # Initialize window attributes
        self.container_window = None
        self.image_window = None
        self.network_window = None
        self.volume_window = None
        self.monitor_windows = {}
        self.monitor_thread = None
        self.service_window = None

        # Initialize logger
        self.logger = logging.getLogger('docker_gui')
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture detailed logs

        file_handler = logging.FileHandler('event_log.log')
        file_handler.setLevel(logging.ERROR)  # Log errors to the file

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # Log info and higher to the console

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.initUi()

    def initUi(self):
        self.setWindowTitle("Docker Management")
        self.setGeometry(100, 100, 800, 600)

        main_layout = QVBoxLayout()
        
        # Create layout for action buttons
        button_layout = QGridLayout()
        
        buttons = [
            ("List Containers", self.list_containers),
            ("Create Container", self.create_container_prompt),
            ("List Images", self.list_images),
            ("List Networks", self.list_networks),
            ("List Volumes", self.list_volumes),
            ("Create Network", self.create_network_prompt),
            ("Create Volume", self.create_volume_prompt),
            ("Prune Unused Volumes", self.prune_volumes),
            ("Create Compose File", self.create_compose_form),
        ]

        # Add buttons to the grid layout
        row = 0
        col = 0
        for text, func in buttons:
            button = QPushButton(text, self)
            button.clicked.connect(func)
            button_layout.addWidget(button, row, col)
            col += 1
            if col > 2:  # Number of columns before wrapping to the next row
                col = 0
                row += 1
        
        # Add the button layout to the main layout
        main_layout.addLayout(button_layout)
        
        # Add QTextEdit for output messages
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        main_layout.addWidget(self.result_text)
        
        self.setLayout(main_layout)

    def display_result(self, result):
        self.result_text.append(result)
    
    def log_error(self, message):
        self.logger.error(message)
        self.display_result(message)

    def log_info(self, message):
        self.logger.info(message)
        self.display_result(message)

    def log_debug(self, message):
        self.logger.debug(message)
        self.display_result(message)

    def list_containers(self):
        try:
            self.logger.info("Listing all containers.")
            containers = self.docker_client.containers.list(all=True)
            self.show_containers_table(containers)
        except docker.errors.APIError as e:
            self.log_error(f"Error listing containers: {e}")

    def show_containers_table(self, containers):
        if self.container_window:
            self.container_window.close()

        self.container_window = QWidget()
        self.container_window.setWindowTitle("Containers")
        self.container_window.setGeometry(100, 100, 1300, 600)

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setRowCount(len(containers))
        table.setColumnCount(13)
        table.setHorizontalHeaderLabels([
            "ID", "Name", "Status", "Start", "Stop", "Pause", "Unpause",
            "Logs", "Shell", "Remove", "Inspect", "Stats", "Monitor"
        ])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for row, container in enumerate(containers):
            table.setItem(row, 0, QTableWidgetItem(container.id))
            table.setItem(row, 1, QTableWidgetItem(container.name))
            table.setItem(row, 2, QTableWidgetItem(container.status))

            buttons = {
                "Start": (3, self.start_container),
                "Stop": (4, self.stop_container),
                "Pause": (5, self.pause_container),
                "Unpause": (6, self.unpause_container),
                "Logs": (7, self.open_logs),
                "Shell": (8, self.open_shell),
                "Remove": (9, self.remove_container),
                "Inspect": (10, self.inspect_container),
                "Stats": (11, self.show_stats),
                "Monitor": (12, self.open_monitor)
            }

            for text, (col, action) in buttons.items():
                button = QPushButton(text)
                button.clicked.connect(lambda _, c=container, a=action: a(c))
                table.setCellWidget(row, col, button)

        layout.addWidget(table)
        self.container_window.setLayout(layout)
        self.container_window.show()

    def list_images(self):
        try:
            self.logger.info("Listing all images.")
            images = self.docker_client.images.list()
            self.show_images_table(images)
        except docker.errors.APIError as e:
            self.log_error(f"Error listing images: {e}")

    def show_images_table(self, images):
        if self.image_window:
            self.image_window.close()

        self.image_window = QWidget()
        self.image_window.setWindowTitle("Images")
        self.image_window.setGeometry(100, 100, 1000, 600)

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setRowCount(len(images))
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["ID", "Tags", "Remove", "Tag", "Push", "Pull"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for row, img in enumerate(images):
            image_id = img.id
            tags = img.tags if img.tags else []

            table.setItem(row, 0, QTableWidgetItem(image_id))
            table.setItem(row, 1, QTableWidgetItem(", ".join(tags)))

            buttons = {
                "Remove": (2, self.remove_image),
                "Tag": (3, self.tag_image),
                "Push": (4, self.push_image),
                "Pull": (5, self.pull_image)
            }

            for text, (col, action) in buttons.items():
                button = QPushButton(text)
                button.clicked.connect(lambda _, i=img, a=action: a(i))
                table.setCellWidget(row, col, button)

        layout.addWidget(table)
        self.image_window.setLayout(layout)
        self.image_window.show()

    def list_networks(self):
        try:
            self.logger.info("Listing all networks.")
            networks = self.docker_client.networks.list()
            self.show_networks_table(networks)
        except docker.errors.APIError as e:
            self.log_error(f"Error listing networks: {e}")

    def show_networks_table(self, networks):
        if self.network_window:
            self.network_window.close()

        self.network_window = QWidget()
        self.network_window.setWindowTitle("Networks")
        self.network_window.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setRowCount(len(networks))
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Name", "ID", "Driver", "Scope", "Inspect", "Remove"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for row, network in enumerate(networks):
            table.setItem(row, 0, QTableWidgetItem(network.name))
            table.setItem(row, 1, QTableWidgetItem(network.id))
            table.setItem(row, 2, QTableWidgetItem(network.attrs.get('Driver', '')))
            table.setItem(row, 3, QTableWidgetItem(network.attrs.get('Scope', '')))

            buttons = {
                "Inspect": (4, self.inspect_network),
                "Remove": (5, self.remove_network_prompt)
            }

            for text, (col, action) in buttons.items():
                button = QPushButton(text)
                button.clicked.connect(lambda _, n=network, a=action: a(n))
                table.setCellWidget(row, col, button)

        layout.addWidget(table)
        self.network_window.setLayout(layout)
        self.network_window.show()

    def list_volumes(self):
        try:
            self.logger.info("Listing all volumes.")
            volumes = self.docker_client.volumes.list()
            self.show_volumes_table(volumes)
        except docker.errors.APIError as e:
            self.log_error(f"Error listing volumes: {e}")

    def show_volumes_table(self, volumes):
        if self.volume_window:
            self.volume_window.close()

        self.volume_window = QWidget()
        self.volume_window.setWindowTitle("Volumes")
        self.volume_window.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setRowCount(len(volumes))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Name", "ID", "Driver", "Remove"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for row, volume in enumerate(volumes):
            table.setItem(row, 0, QTableWidgetItem(volume.name))
            table.setItem(row, 1, QTableWidgetItem(volume.id))
            table.setItem(row, 2, QTableWidgetItem(volume.attrs.get('Driver', '')))

            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(lambda _, v=volume: self.remove_volume_prompt(v))
            table.setCellWidget(row, 3, remove_button)

        layout.addWidget(table)
        self.volume_window.setLayout(layout)
        self.volume_window.show()

    def prune_volumes(self):
        try:
            self.logger.info("Pruning unused volumes.")
            result = self.docker_client.volumes.prune()
            self.log_info(f"Pruned volumes: {result}")
        except docker.errors.APIError as e:
            self.log_error(f"Error pruning volumes: {e}")


    def create_container_prompt(self):
        try:
            self.logger.info("Prompting user to create a new container.")

            # Create the dialog box for multiple inputs
            dialog = QDialog(self)
            dialog.setWindowTitle("Create Container")

            layout = QVBoxLayout(dialog)

            # Container Name Input
            container_name_label = QLabel("Container Name:")
            container_name_input = QLineEdit(dialog)
            layout.addWidget(container_name_label)
            layout.addWidget(container_name_input)

            # Dockerfile Path Input
            dockerfile_label = QLabel("Dockerfile Path:")
            dockerfile_input = QLineEdit(dialog)
            dockerfile_browse_btn = QPushButton("Browse", dialog)
            dockerfile_browse_btn.clicked.connect(lambda: self.browse_dockerfile(dockerfile_input))

            dockerfile_layout = QHBoxLayout()
            dockerfile_layout.addWidget(dockerfile_input)
            dockerfile_layout.addWidget(dockerfile_browse_btn)

            layout.addWidget(dockerfile_label)
            layout.addLayout(dockerfile_layout)

            # Flags Input (Optional)
            flags_label = QLabel("Additional Flags (optional):")
            flags_input = QLineEdit(dialog)
            layout.addWidget(flags_label)
            layout.addWidget(flags_input)

            # OK and Cancel buttons
            button_layout = QHBoxLayout()
            ok_button = QPushButton("Create", dialog)
            cancel_button = QPushButton("Cancel", dialog)

            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)

            layout.addLayout(button_layout)

            # Handle OK and Cancel clicks
            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)

            # Show dialog and check result
            if dialog.exec_() == QDialog.Accepted:
                container_name = container_name_input.text()
                dockerfile_path = dockerfile_input.text()
                flags = flags_input.text()

                # Ensure container name and dockerfile path are provided
                if container_name and dockerfile_path:
                    self.create_container_from_dockerfile(container_name, dockerfile_path, flags)
                else:
                    self.log_error("Container name and Dockerfile path are required to create a container.")

        except Exception as e:
            self.log_error(f"Error creating container: {e}")

    def browse_dockerfile(self, dockerfile_input):
        # Open file dialog to select Dockerfile path
        dockerfile_path, _ = QFileDialog.getOpenFileName(self, "Select Dockerfile", "", "Dockerfile (*.Dockerfile);;All Files (*)")
        if dockerfile_path:
            dockerfile_input.setText(dockerfile_path)

    def create_container_from_dockerfile(self, container_name, dockerfile_path, flags=None):
        try:
            self.logger.info(f"Building image from Dockerfile at: {dockerfile_path}")

            # Extract directory and Dockerfile filename
            dockerfile_dir = os.path.dirname(dockerfile_path)
            dockerfile_name = os.path.basename(dockerfile_path)

            # Build the image from Dockerfile
            try:
                image, build_logs = self.docker_client.images.build(
                    path=dockerfile_dir, dockerfile=dockerfile_name, tag=container_name
                )
                for log in build_logs:
                    self.logger.info(log.get("stream", "").strip())  # Log the build output
                self.logger.info(f"Image '{container_name}' built successfully from Dockerfile.")
            except docker.errors.BuildError as e:
                self.log_error(f"Failed to build image from Dockerfile: {e}")
                return

            # Prepare container arguments
            run_args = {'detach': True, 'name': container_name}

            if flags:
                # Process flags and add to the arguments as needed
                self.logger.info(f"Running container with flags: {flags}")
                # Example: split the flags string by spaces
                flag_list = flags.split()
                run_args.update({'command': flag_list})

            # Run the container from the built image
            self.docker_client.containers.run(container_name, **run_args)
            self.log_info(f"Container '{container_name}' created successfully.")

        except docker.errors.APIError as e:
            self.log_error(f"Error creating container: {e}")


    def create_container(self, container_name, image_name, dockerfile_path=None, flags=None):
        try:
            self.logger.info(f"Creating container with name: {container_name} and image: {image_name}")

            # If a Dockerfile is provided, build the image first
            if dockerfile_path:
                self.logger.info(f"Building image from Dockerfile at: {dockerfile_path}")

                # Use Docker's SDK to build the image from the Dockerfile
                try:
                    image, logs = self.docker_client.images.build(path=dockerfile_path, tag=image_name)
                    for log in logs:
                        self.logger.info(log.get("stream", "").strip())  # Log the build output
                    self.logger.info(f"Image '{image_name}' built successfully from Dockerfile.")
                except docker.errors.BuildError as e:
                    self.log_error(f"Failed to build image from Dockerfile: {e}")
                    return

            # Prepare container arguments
            run_args = {'detach': True, 'name': container_name}

            if flags:
                # Process flags and add to the arguments as needed
                self.logger.info(f"Running container with flags: {flags}")
                # Example: split the flags string by spaces
                flag_list = flags.split()
                run_args.update({'command': flag_list})

            self.log_info(f"Container '{container_name}' created successfully.")

        except docker.errors.APIError as e:
            self.log_error(f"Error creating container: {e}")


    def deploy_compose_prompt(self):
        try:
            self.logger.info("Prompting user to deploy a Docker Compose file.")
            file_path, _ = QFileDialog.getOpenFileName(self, "Open Docker Compose File", "", "YAML Files (*.yml *.yaml)")
            if file_path:
                self.deploy_compose(file_path)
        except Exception as e:
            self.log_error(f"Error deploying compose file: {e}")

    def create_network_prompt(self):
        try:
            self.logger.info("Prompting user to create a new network.")
            network_name, ok = QInputDialog.getText(self, "Create Network", "Network name:")
            if ok and network_name:
                self.create_network(network_name)
        except Exception as e:
            self.log_error(f"Error creating network: {e}")

    def create_network(self, network_name):
        try:
            self.logger.info(f"Creating network with name: {network_name}")
            self.docker_client.networks.create(name=network_name, driver="bridge")
            self.log_info(f"Network '{network_name}' created successfully.")
        except docker.errors.APIError as e:
            self.log_error(f"Error creating network: {e}")

    def create_volume_prompt(self):
        try:
            self.logger.info("Prompting user to create a new volume.")
            volume_name, ok = QInputDialog.getText(self, "Create Volume", "Volume name:")
            if ok and volume_name:
                self.create_volume(volume_name)
        except Exception as e:
            self.log_error(f"Error creating volume: {e}")

    def create_volume(self, volume_name):
        try:
            self.logger.info(f"Creating volume with name: {volume_name}")
            self.docker_client.volumes.create(name=volume_name)
            self.log_info(f"Volume '{volume_name}' created successfully.")
        except docker.errors.APIError as e:
            self.log_error(f"Error creating volume: {e}")

    def run_container(self, container):
        try:
            container.start()
            self.log_info(f"Container '{container.id}' started.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.log_error(f"Error starting container: {e}")

    def start_container(self, container):
        try:
            container.start()
            self.log_info(f"Container '{container.id}' started.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.log_error(f"Error starting container: {e}")

    def stop_container(self, container):
        try:
            container.stop()
            self.log_info(f"Container '{container.id}' stopped.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.log_error(f"Error stopping container: {e}")

    def pause_container(self, container):
        try:
            container.pause()
            self.log_info(f"Container '{container.id}' paused.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.log_error(f"Error pausing container: {e}")

    def unpause_container(self, container):
        try:
            container.unpause()
            self.log_info(f"Container '{container.id}' unpaused.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.log_error(f"Error unpausing container: {e}")

    def remove_container(self, container):
        try:
            self.logger.info(f"Removing container with ID: {container.id}")
            container.remove(force=True)
            self.log_info(f"Container '{container.name}' removed successfully.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.log_error(f"Error removing container: {e}")


    def open_logs(self, container):
        try:
            self.logger.info(f"Opening logs for container with ID: {container.id}")
            logs = container.logs().decode('utf-8')
            self.display_result(f"Logs for container {container.id}:\n{logs}")
        except docker.errors.APIError as e:
            self.log_error(f"Error opening logs for container: {e}")

    def open_shell(self, container):
        try:
            self.logger.info(f"Opening shell for container with ID: {container.id}")
            command = f"docker exec -it {container.id} /bin/bash"
            open_terminal_with_command(command)

        except Exception as e:
            self.log_error(f"Error opening shell for container: {e}")

    def remove_image(self, image):
        try:
            self.logger.info(f"Removing image with ID: {image.id}")
            self.docker_client.images.remove(image.id, force=True)
            self.log_info(f"Image '{image.id}' removed successfully.")
            self.list_images()
        except docker.errors.APIError as e:
            self.log_error(f"Error removing image: {e}")

    def tag_image(self, image):
        try:
            self.logger.info(f"Prompting user to tag image with ID: {image.id}")
            tag, ok = QInputDialog.getText(self, "Tag Image", "New tag:")
            if ok and tag:
                self.logger.info(f"Tagging image with ID: {image.id} with tag: {tag}")
                image.tag(tag)
                self.log_info(f"Image '{image.id}' tagged with '{tag}' successfully.")
        except docker.errors.APIError as e:
            self.log_error(f"Error tagging image: {e}")

    def push_image(self, image):
        try:
            self.logger.info(f"Prompting user to push image with ID: {image.id}")
            repository, ok = QInputDialog.getText(self, "Push Image", "Repository:")
            if ok and repository:
                self.logger.info(f"Pushing image with ID: {image.id} to repository: {repository}")
                self.docker_client.images.push(repository)
                self.log_info(f"Image '{image.id}' pushed to repository '{repository}' successfully.")
        except docker.errors.APIError as e:
            self.log_error(f"Error pushing image: {e}")

    def pull_image(self, image):
        try:
            self.logger.info(f"Prompting user to pull image with ID: {image.id}")
            repository, ok = QInputDialog.getText(self, "Pull Image", "Repository:")
            if ok and repository:
                self.logger.info(f"Pulling image from repository: {repository}")
                self.docker_client.images.pull(repository)
                self.log_info(f"Image pulled from repository '{repository}' successfully.")
        except docker.errors.APIError as e:
            self.log_error(f"Error pulling image: {e}")

    def inspect_container(self, container):
        try:
            self.logger.info(f"Inspecting container with ID: {container.id}")
            info = container.attrs
            self.display_result(f"Inspecting container {container.id}:\n{info}")
        except docker.errors.APIError as e:
            self.log_error(f"Error inspecting container: {e}")

    def show_stats(self, container):
        try:
            self.logger.info(f"Showing stats for container with ID: {container.id}")
            stats = container.stats(stream=False)
            self.display_result(f"Stats for container {container.id}:\n{stats}")
        except docker.errors.APIError as e:
            self.log_error(f"Error showing stats for container: {e}")



    def open_monitor(self, container):
        try:
            container_id = container.id

            # Check if the container is running
            if container.status != 'running':
                self.logger.error(f"Cannot open resource monitor: Container {container_id} is not running.")
                self.display_result(f"Cannot open resource monitor: Container {container_id} is not running.")
                return

            self.logger.info(f"Opening resource monitor for container: {container_id}")

            if container_id not in self.monitor_windows or not self.monitor_windows[container_id]:
                monitor_window = QWidget()
                monitor_window.setWindowTitle(f"Resource Monitor for {container.name}")
                monitor_window.setGeometry(100, 100, 800, 600)

                layout = QVBoxLayout()
                resource_graph = ResourceGraphWidget(container.name)
                layout.addWidget(resource_graph)

                monitor_thread = ResourceMonitorThread(container)
                monitor_thread.update_graph.connect(resource_graph.update_graph)
                monitor_thread.start()

                monitor_window.setLayout(layout)
                monitor_window.show()

                # Save the window and the thread in the dictionary
                self.monitor_windows[container_id] = (monitor_window, monitor_thread)
            else:
                # If the window already exists, bring it to the front
                self.monitor_windows[container_id][0].show()
        except Exception as e:
            self.logger.error(f"Error opening resource monitor: {e}")



    def inspect_network(self, network):
        try:
            self.logger.info(f"Inspecting network with ID: {network.id}")
            info = network.attrs
            self.display_result(f"Inspecting network {network.id}:\n{info}")
        except docker.errors.APIError as e:
            self.log_error(f"Error inspecting network: {e}")

    def remove_network_prompt(self, network):
        try:
            self.logger.info(f"Prompting user to remove network with ID: {network.id}")
            reply = QMessageBox.question(self, 'Remove Network',
                                         f"Are you sure you want to remove network '{network.name}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove_network(network)
        except Exception as e:
            self.log_error(f"Error prompting network removal: {e}")

    def remove_network(self, network):
        try:
            self.logger.info(f"Removing network with ID: {network.id}")
            network.remove()
            self.log_info(f"Network '{network.id}' removed successfully.")
            self.list_networks()
        except docker.errors.APIError as e:
            self.log_error(f"Error removing network: {e}")

    def remove_volume_prompt(self, volume):
        try:
            self.logger.info(f"Prompting user to remove volume with ID: {volume.id}")
            reply = QMessageBox.question(self, 'Remove Volume',
                                         f"Are you sure you want to remove volume '{volume.name}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove_volume(volume)
        except Exception as e:
            self.log_error(f"Error prompting volume removal: {e}")

    def remove_volume(self, volume):
        try:
            self.logger.info(f"Removing volume with ID: {volume.id}")
            self.docker_client.volumes.get(volume.id).remove()
            self.log_info(f"Volume '{volume.id}' removed successfully.")
            self.list_volumes()
        except docker.errors.APIError as e:
            self.log_error(f"Error removing volume: {e}")


    def manage_docker_compose_services(self):
        services = self.list_docker_compose_services()

        if not self.service_window:
            self.service_window = QWidget()
            self.service_window.setWindowTitle("Docker Compose Services")
            self.service_window.setGeometry(100, 100, 1500, 600)

            # Create layout and table
            layout = QVBoxLayout()
            layout.setContentsMargins(10, 10, 10, 10)  # Set margin to ensure no clipping
            layout.setSpacing(5)  # Reduce spacing if it's too wide
            
            table = QTableWidget()
            table.setRowCount(len(services))
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels([
                "Service Name", "Status", "Start", "Stop", "View Logs"
            ])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            for row, service in enumerate(services):
                name = service['name']
                status = service['status']

                table.setItem(row, 0, QTableWidgetItem(name))
                table.setItem(row, 1, QTableWidgetItem(status))

                # Start Button
                start_button = QPushButton("Start")
                start_button.clicked.connect(lambda _, s=name: self.start_service(s))
                table.setCellWidget(row, 2, start_button)

                # Stop Button
                stop_button = QPushButton("Stop")
                stop_button.clicked.connect(lambda _, s=name: self.stop_service(s))
                table.setCellWidget(row, 3, stop_button)

                # View Logs Button
                view_logs_button = QPushButton("View Logs")
                view_logs_button.clicked.connect(lambda _, s=name: self.view_service_logs(s))
                table.setCellWidget(row, 4, view_logs_button)

            # Add table to layout first
            layout.addWidget(table)

            # Add QTextEdit for output messages at the bottom
            self.result_text = QTextEdit()
            self.result_text.setReadOnly(True)
            layout.addWidget(self.result_text)

            # Set the layout to the window
            self.service_window.setLayout(layout)
        else:
            self.service_window.show()

    def start_service(self, service_name):
        """
        Starts the specified Docker Compose service.
        """
        try:
            result = subprocess.run(['docker-compose', 'up', '-d', service_name],
                                    capture_output=True, text=True, check=True)
            self.result_text.append(f"Service '{service_name}' started successfully.")
            self.logger.info(f"Service '{service_name}' started.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to start service '{service_name}': {e.stderr}")
            self.result_text.append(f"Error starting service '{service_name}': {e.stderr}")

    def stop_service(self, service_name):
        """
        Stops the specified Docker Compose service.
        """
        try:
            result = subprocess.run(['docker-compose', 'stop', service_name],
                                    capture_output=True, text=True, check=True)
            self.result_text.append(f"Service '{service_name}' stopped successfully.")
            self.logger.info(f"Service '{service_name}' stopped.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to stop service '{service_name}': {e.stderr}")
            self.result_text.append(f"Error stopping service '{service_name}': {e.stderr}")

    def view_service_logs(self, service_name):
        """
        Fetches and displays logs for the specified Docker Compose service.
        """
        try:
            result = subprocess.run(['docker-compose', 'logs', service_name],
                                    capture_output=True, text=True, check=True)
            self.result_text.setPlainText(f"Logs for service '{service_name}':\n{result.stdout}")
            self.logger.info(f"Logs for service '{service_name}' retrieved.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to fetch logs for service '{service_name}': {e.stderr}")
            self.result_text.append(f"Error fetching logs for service '{service_name}': {e.stderr}")
        except Exception as e:
            self.logger.error(f"Unexpected error while fetching logs: {e}")
            self.result_text.append(f"Unexpected error: {e}")


    def create_compose_form(self):
        """
        Create a detailed form for generating Docker Compose YAML with every possible setting.
        """
        self.compose_window = QWidget()
        self.compose_window.setWindowTitle("Create Docker Compose YAML")
        self.compose_window.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # Service Name
        self.service_name_input = QLineEdit()
        layout.addWidget(QLabel("Service Name:"))
        layout.addWidget(self.service_name_input)

        # Image Name
        self.image_name_input = QLineEdit()
        layout.addWidget(QLabel("Image Name:"))
        layout.addWidget(self.image_name_input)

        # Ports
        self.ports_input = QLineEdit()
        layout.addWidget(QLabel("Ports (e.g., 80:80, 6379:6379):"))
        layout.addWidget(self.ports_input)

        # Environment Variables
        self.env_input = QLineEdit()
        layout.addWidget(QLabel("Environment Variables (e.g., KEY=VALUE,KEY2=VALUE2):"))
        layout.addWidget(self.env_input)

        # Volumes
        self.volumes_input = QLineEdit()
        layout.addWidget(QLabel("Volumes (e.g., ./host_path:/container_path):"))
        layout.addWidget(self.volumes_input)

        # Networks
        self.network_input = QLineEdit()
        layout.addWidget(QLabel("Networks (optional):"))
        layout.addWidget(self.network_input)

        # Command
        self.command_input = QLineEdit()
        layout.addWidget(QLabel("Command (optional):"))
        layout.addWidget(self.command_input)

        # Restart Policy
        self.restart_policy_input = QLineEdit()
        layout.addWidget(QLabel("Restart Policy (e.g., always, on-failure):"))
        layout.addWidget(self.restart_policy_input)

        # **Replicas** input
        self.replicas_input = QLineEdit()
        layout.addWidget(QLabel("Replicas (e.g., 1, 3):"))
        layout.addWidget(self.replicas_input)

        # Button to generate YAML
        generate_button = QPushButton("Generate YAML")
        generate_button.clicked.connect(self.generate_full_docker_compose_yaml)
        layout.addWidget(generate_button)

        # Output area for YAML preview
        self.yaml_output = QTextEdit()
        self.yaml_output.setReadOnly(True)
        layout.addWidget(QLabel("Generated YAML:"))
        layout.addWidget(self.yaml_output)

        # Button to deploy
        deploy_button = QPushButton("Deploy Compose File")
        deploy_button.clicked.connect(self.save_and_deploy_yaml)
        layout.addWidget(deploy_button)

        self.compose_window.setLayout(layout)
        self.compose_window.show()

    def generate_full_docker_compose_yaml(self):
        """
        Generates a full Docker Compose YAML with all settings from the form and displays it.
        """
        # Collect inputs
        service_name = self.service_name_input.text()
        image_name = self.image_name_input.text()
        ports = self.ports_input.text().split(',') if self.ports_input.text() else []
        env_vars = self.env_input.text().split(',') if self.env_input.text() else []
        volumes = self.volumes_input.text().split(',') if self.volumes_input.text() else []
        networks = self.network_input.text() if self.network_input.text() else None
        command = self.command_input.text() if self.command_input.text() else None
        restart_policy = self.restart_policy_input.text() if self.restart_policy_input.text() else None
        replicas = self.replicas_input.text() if self.replicas_input.text() else None

        if not service_name or not image_name:
            self.yaml_output.setPlainText("Please provide both service name and image name.")
            return

        # Construct the compose dictionary
        service_config = {
            'image': image_name,
            'ports': ports,
            'environment': env_vars,
            'volumes': volumes
        }

        # Add optional fields
        if networks:
            service_config['networks'] = [networks]
        if command:
            service_config['command'] = command
        if restart_policy or replicas:
            service_config['deploy'] = {}
            if restart_policy:
                service_config['deploy']['restart_policy'] = {'condition': restart_policy}
            if replicas:
                service_config['deploy']['replicas'] = int(replicas)

        # Compose file structure
        compose_dict = {
            'version': '3',
            'services': {
                service_name: service_config
            }
        }

        # Convert the dictionary to YAML format
        yaml_str = yaml.dump(compose_dict, default_flow_style=False)
        self.yaml_output.setPlainText(yaml_str)

        # Store the YAML for deployment
        self.generated_yaml = yaml_str

    def save_and_deploy_yaml(self):
        """
        Saves the generated YAML to a file and deploys it using Docker Compose.
        """
        # Open file dialog to save the YAML
        file_path, _ = QFileDialog.getSaveFileName(self.compose_window, "Save Compose File", "", "YAML Files (*.yaml)")
        
        if file_path:
            try:
                # Save the generated YAML to the selected file
                with open(file_path, 'w') as yaml_file:
                    yaml_file.write(self.generated_yaml)

                # Deploy the saved Docker Compose file
                self.deploy_compose(file_path)
            except Exception as e:
                self.yaml_output.setPlainText(f"Error saving or deploying Docker Compose file: {str(e)}")


    def deploy_compose(self, file_path):
        """
        Deploys the provided Docker Compose YAML file.
        """
        try:
            self.logger.info(f"Deploying Docker Compose file: {file_path}")
            result = subprocess.run(["docker-compose", "-f", file_path, "up", "-d"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_info(f"Successfully deployed Docker Compose file: {file_path}")
            else:
                self.log_error(f"Failed to deploy Docker Compose file: {result.stderr}")
        except subprocess.CalledProcessError as e:
            self.log_error(f"Error deploying Docker Compose file: {e}")