import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout, 
    QLineEdit, QLabel, QDialog, QFileDialog, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal
import os
import sys
import time

import docker
from docker.errors import APIError as DockerAPIError
import subprocess

from docker_client import get_docker_client
from resource_monitor import ResourceGraphWidget, ResourceMonitorThread
from terminal_utils import terminal_emulator, open_terminal_with_command


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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

        # Initialize logger
        self.logger = logging.getLogger('docker_gui')
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture detailed logs

        file_handler = logging.FileHandler('docker_gui.log')
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

        layout = QVBoxLayout()
        button_layout = QHBoxLayout()

        buttons = [
            ("List Containers", self.list_containers),
            ("Create Container", self.create_container_prompt),
            ("Deploy Compose File", self.deploy_compose_prompt),
            ("List Images", self.list_images),
            ("List Networks", self.list_networks),
            ("List Volumes", self.list_volumes),
            ("Create Network", self.create_network_prompt),
            ("Create Volume", self.create_volume_prompt),
            ("Prune Unused Volumes", self.prune_volumes),
        ]

        for text, func in buttons:
            button = QPushButton(text, self)
            button.clicked.connect(func)
            button_layout.addWidget(button)

        layout.addLayout(button_layout)
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)
        self.setLayout(layout)



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
            container_name, ok = QInputDialog.getText(self, "Create Container", "Container name:")
            if ok and container_name:
                image_name, ok = QInputDialog.getText(self, "Create Container", "Image name:")
                if ok and image_name:
                    self.create_container(container_name, image_name)
        except Exception as e:
            self.log_error(f"Error creating container: {e}")

    def create_container(self, container_name, image_name):
        try:
            self.logger.info(f"Creating container with name: {container_name} and image: {image_name}")
            self.docker_client.containers.run(image_name, name=container_name, detach=True)
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

    def deploy_compose(self, file_path):
        try:
            self.logger.info(f"Deploying Docker Compose file: {file_path}")
            result = subprocess.run(["docker-compose", "-f", file_path, "up", "-d"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_info(f"Successfully deployed Docker Compose file: {file_path}")
            else:
                self.log_error(f"Failed to deploy Docker Compose file: {result.stderr}")
        except subprocess.CalledProcessError as e:
            self.log_error(f"Error deploying Docker Compose file: {e}")

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
            self.log_info(f"Container '{container.id}' removed successfully.")
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
        except docker.errors.APIError as e:
            self.log_error(f"Error removing volume: {e}")



