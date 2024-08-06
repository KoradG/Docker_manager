from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout, 
    QLineEdit, QLabel, QDialog, QFileDialog, QMessageBox
)
from docker_client import get_docker_client
from resource_monitor import ResourceGraphWidget, ResourceMonitorThread
from terminal_utils import terminal_emulator
import docker
import sys
import subprocess
from docker_client import DockerClient


class DockerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.docker_client = get_docker_client()
        
        # Initialize window attributes
        self.container_window = None
        self.image_window = None
        self.network_window = None
        self.volume_window = None
        self.create_volume_dialog = None
        self.create_network_dialog = None
        self.monitor_window = None
        self.monitor_thread = None

        self.initUI()

    def initUI(self):
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



    def list_containers(self):
        try:
            containers = self.docker_client.list_containers()
            self.show_containers_table(containers)
        except docker.errors.APIError as e:
            self.display_result(f"Error listing containers: {e}")

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

            start_button = self.create_action_button("Start", container, self.start_container)
            stop_button = self.create_action_button("Stop", container, self.stop_container)
            pause_button = self.create_action_button("Pause", container, self.pause_container)
            unpause_button = self.create_action_button("Unpause", container, self.unpause_container)
            logs_button = self.create_action_button("Logs", container, self.open_logs)
            shell_button = self.create_action_button("Shell", container, self.open_shell)
            remove_button = self.create_action_button("Remove", container, self.remove_container)
            inspect_button = self.create_action_button("Inspect", container, self.inspect_container)
            stats_button = self.create_action_button("Stats", container, self.show_stats)
            monitor_button = self.create_action_button("Monitor", container, self.open_monitor)

            table.setCellWidget(row, 3, start_button)
            table.setCellWidget(row, 4, stop_button)
            table.setCellWidget(row, 5, pause_button)
            table.setCellWidget(row, 6, unpause_button)
            table.setCellWidget(row, 7, logs_button)
            table.setCellWidget(row, 8, shell_button)
            table.setCellWidget(row, 9, remove_button)
            table.setCellWidget(row, 10, inspect_button)
            table.setCellWidget(row, 11, stats_button)
            table.setCellWidget(row, 12, monitor_button)

        layout.addWidget(table)
        self.container_window.setLayout(layout)
        self.container_window.show()


    def list_images(self):
        images = self.docker_client.list_images()
        self.show_images_table(images)

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
            table.setItem(row, 0, QTableWidgetItem(img['id']))
            table.setItem(row, 1, QTableWidgetItem(", ".join(img['tags'])))

            table.setCellWidget(row, 2, self.create_action_button("Remove", img, self.remove_image))
            table.setCellWidget(row, 3, self.create_action_button("Tag", img, self.tag_image))
            table.setCellWidget(row, 4, self.create_action_button("Push", img, self.push_image))
            table.setCellWidget(row, 5, self.create_action_button("Pull", img, self.pull_image))

        layout.addWidget(table)
        self.image_window.setLayout(layout)
        self.image_window.show()

    def list_networks(self):
        try:
            networks = self.docker_client.list_networks()
            self.show_networks_table(networks)
        except docker.errors.APIError as e:
            self.display_result(f"Error listing networks: {e}")

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
            network_info = network.attrs
            table.setItem(row, 0, QTableWidgetItem(network.name))
            table.setItem(row, 1, QTableWidgetItem(network.id))
            table.setItem(row, 2, QTableWidgetItem(network_info.get('Driver', '')))
            table.setItem(row, 3, QTableWidgetItem(network_info.get('Scope', '')))

            inspect_button = self.create_action_button("Inspect", network, self.inspect_network)
            remove_button = self.create_action_button("Remove", network, self.remove_network_prompt)

            table.setCellWidget(row, 4, inspect_button)
            table.setCellWidget(row, 5, remove_button)

        layout.addWidget(table)
        self.network_window.setLayout(layout)
        self.network_window.show()

    def list_volumes(self):
        volumes = self.docker_client.list_volumes()
        self.show_volumes_table(volumes)

    def show_volumes_table(self, volumes):
        if self.volume_window and self.volume_window.isVisible():
            self.volume_window.close()

        self.volume_window = QWidget()
        self.volume_window.setWindowTitle("Volumes")
        self.volume_window.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()
        
        table = QTableWidget()
        table.setRowCount(len(volumes))
        table.setColumnCount(5)  # Adjust column count to include action buttons
        table.setHorizontalHeaderLabels(["Name", "Driver", "Mountpoint", "Inspect", "Remove"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for row, volume in enumerate(volumes):
            table.setItem(row, 0, QTableWidgetItem(volume['name']))
            table.setItem(row, 1, QTableWidgetItem(volume['driver']))
            table.setItem(row, 2, QTableWidgetItem(volume['mountpoint']))

            # Create and add action buttons
            inspect_button = self.create_action_button("Inspect", volume, self.inspect_volume)
            remove_button = self.create_action_button("Remove", volume, self.remove_volume)

            table.setCellWidget(row, 3, inspect_button)
            table.setCellWidget(row, 4, remove_button)

        layout.addWidget(table)

        # If the volume window already has a layout, clear it
        if self.volume_window.layout() is not None:
            self.clear_layout(self.volume_window.layout())

        self.volume_window.setLayout(layout)
        self.volume_window.show()

    def clear_layout(layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    clear_layout(item.layout())

    def create_action_button(self, text, volume, func):
        button = QPushButton(text)
        button.clicked.connect(lambda: func(volume))
        return button

    def inspect_volume(self, volume):
        volume_info = self.docker_client.inspect_volume(volume['name'])
        self.display_result(f"Volume Info: {volume_info}")

    def remove_volume(self, volume):
        volume_name = volume['name']

        reply = QMessageBox.question(self, 'Remove Volume',
                                    f"Are you sure you want to remove the volume '{volume_name}'?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                self.docker_client.remove_volume(volume_name)
                self.list_volumes()  # Refresh the list
            except docker.errors.APIError as e:
                self.display_result(f"Error removing volume: {e}")


    def prune_volumes(self):
        try:
            self.docker_client.prune_volumes()
            self.display_result("Unused volumes pruned successfully.")
            self.list_volumes()  # Refresh list
        except docker.errors.APIError as e:
            self.display_result(f"Error pruning volumes: {e}")



    def create_action_button(self, label, item, action):
        button = QPushButton(label, self)
        button.clicked.connect(lambda: action(item))
        return button

    def start_container(self, container):
        try:
            container.start()
            self.display_result(f"Container {container.name} started successfully.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.display_result(f"Error starting container: {e}")

    def stop_container(self, container):
        try:
            container.stop()
            self.display_result(f"Container {container.name} stopped successfully.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.display_result(f"Error stopping container: {e}")

    def pause_container(self, container):
        try:
            container.pause()
            self.display_result(f"Container {container.name} paused successfully.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.display_result(f"Error pausing container: {e}")

    def unpause_container(self, container):
        try:
            container.unpause()
            self.display_result(f"Container {container.name} unpaused successfully.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.display_result(f"Error unpausing container: {e}")

    def open_logs(self, container):
        logs = container.logs()
        self.display_result(f"Logs for {container.name}:\n{logs.decode('utf-8')}")

    def open_shell(self, container):
        try:
            terminal_command = f"{terminal_emulator} -e 'docker exec -it {container.id} /bin/bash'"
            subprocess.Popen(terminal_command, shell=True)
        except Exception as e:
            self.display_result(f"Error occurred while opening terminal with shell: {e}")

    def remove_container(self, container):
        try:
            container.remove()
            self.display_result(f"Container {container.name} removed successfully.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.display_result(f"Error removing container: {e}")

    def inspect_container(self, container):
        details = container.attrs
        self.display_result(f"Details for {container.name}:\n{details}")

    def show_stats(self, container):
        stats = container.stats(stream=False)
        self.display_result(f"Stats for {container.name}:\n{stats}")

    def open_monitor(self, container):
        self.monitor_window = ResourceGraphWidget(container.name)
        self.monitor_window.show()

        self.monitor_thread = ResourceMonitorThread(container)
        self.monitor_thread.update_graph.connect(self.monitor_window.update_graph)
        self.monitor_thread.start()

    def create_container_prompt(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Container")
        dialog.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        form_layout = QFormLayout()
        name_input = QLineEdit()
        image_input = QLineEdit()
        dockerfile_input = QLineEdit()  # New field for Dockerfile location
        build_context_input = QLineEdit()  # New field for build context
        form_layout.addRow("Container Name:", name_input)
        form_layout.addRow("Image Name (if using Dockerfile):", image_input)
        form_layout.addRow("Dockerfile Path:", dockerfile_input)
        form_layout.addRow("Build Context Path:", build_context_input)

        create_button = QPushButton("Create")
        create_button.clicked.connect(lambda: self.create_container(
            name_input.text(), image_input.text(), dockerfile_input.text(), build_context_input.text(), dialog
        ))

        layout.addLayout(form_layout)
        layout.addWidget(create_button)

        dialog.setLayout(layout)
        dialog.exec_()


    def create_container(self, name, image, dockerfile_path, build_context, dialog):
        docker_client = get_docker_client()  # Ensure DockerClient is available

        if dockerfile_path:
            # Build the Docker image from Dockerfile and create the container
            container = docker_client.create_container_from_dockerfile(dockerfile_path)
            if container:
                self.display_result(f"Container created successfully: {container.id}")
        elif image:
            # Create the container using an existing image
            container = docker_client.create_container(image_name=image, command="", env_vars=None, ports=None, volumes=None, network=None)
            if container:
                self.display_result(f"Container created successfully: {container.id}")
        else:
            self.display_result("Error: No Dockerfile or image provided.")

        dialog.close()


    def create_container_from_dockerfile(self, dockerfile_path):
        try:
            if not os.path.isdir(dockerfile_path):
                raise ValueError(f"{dockerfile_path} is not a valid directory.")
            image_tag = "mydockerimage"  # Tag for the built image
            # Build the Docker image from the Dockerfile
            self.build_image_from_dockerfile(dockerfile_path, tag=image_tag)
            # Create the container using the newly built image
            container = self.create_container(image_name=image_tag, command="", env_vars=None, ports=None, volumes=None, network=None)
            return container
        except Exception as e:
            print(f"Error occurred while creating container: {e}", flush=True)
            return None


    def create_container_from_image(self, name, image):
        try:
            container = self.docker_client.create_container(
                image=image,
                name=name,
                detach=True  # Make sure the container runs in detached mode
            )
            self.display_result(f"Container {name} created successfully.")
        except docker.errors.APIError as e:
            self.display_result(f"Error creating container: {e}")



    def deploy_compose_prompt(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Compose File", "", "YAML Files (*.yml *.yaml);;All Files (*)", options=options)
        if file_path:
            self.deploy_compose_file(file_path)

    def deploy_compose_file(self, file_path):
        try:
            result = subprocess.run(["docker-compose", "-f", file_path, "up", "-d"], capture_output=True, text=True)
            self.display_result(result.stdout)
            if result.stderr:
                self.display_result(f"Errors:\n{result.stderr}")
        except subprocess.CalledProcessError as e:
            self.display_result(f"Error deploying compose file: {e}")

    def create_network_prompt(self):
        self.create_network_dialog = QDialog(self)
        self.create_network_dialog.setWindowTitle("Create Network")
        self.create_network_dialog.setGeometry(150, 150, 400, 200)

        layout = QFormLayout()

        self.network_name_input = QLineEdit()
        self.network_driver_input = QLineEdit()

        layout.addRow(QLabel("Network Name:"), self.network_name_input)
        layout.addRow(QLabel("Driver: (Optional)"), self.network_driver_input)

        create_button = QPushButton("Create Network")
        create_button.clicked.connect(lambda: self.create_network(self.network_name_input.text(), self.network_driver_input.text()))
        layout.addWidget(create_button)

        self.create_network_dialog.setLayout(layout)
        self.create_network_dialog.exec_()


    def create_network(self, name, driver):
        try:
            self.docker_client.create_network(name, driver)
            self.display_result(f"Network '{name}' created successfully.")
            self.create_network_dialog.accept()
        except docker.errors.APIError as e:
            self.display_result(f"Error creating network: {e}")


    def create_volume_prompt(self):
        """Prompt user to create a volume."""
        self.create_volume_dialog = QDialog(self)
        self.create_volume_dialog.setWindowTitle("Create Volume")
        self.create_volume_dialog.setGeometry(150, 150, 400, 200)

        layout = QFormLayout()

        self.volume_name_input = QLineEdit()
        self.driver_input = QLineEdit()

        layout.addRow(QLabel("Volume Name:"), self.volume_name_input)
        layout.addRow(QLabel("Driver (optional):"), self.driver_input)

        submit_button = QPushButton("Create Volume")
        submit_button.clicked.connect(self.create_volume_from_dialog)
        layout.addWidget(submit_button)

        self.create_volume_dialog.setLayout(layout)
        self.create_volume_dialog.exec_()


    def create_volume_from_dialog(self):
        volume_name = self.volume_name_input.text()
        driver = self.driver_input.text() or None

        try:
            self.docker_client.create_volume(volume_name, driver=driver)
            self.display_result(f"Volume {volume_name} created successfully.")
            self.list_volumes()  # Refresh list
        except docker.errors.APIError as e:
            self.display_result(f"Error creating volume: {e}")

        self.create_volume_dialog.accept()


    def create_volume(self, name, driver, dialog):
        try:
            volume = self.docker_client.create_volume(name=name, driver=driver)
            self.display_result(f"Volume {volume.name} created successfully.")
            dialog.close()
        except docker.errors.APIError as e:
            self.display_result(f"Error creating volume: {e}")

    def remove_image(self, image):
        try:
            self.docker_client.remove_image(image['id'])
            self.display_result(f"Image {image['id']} removed successfully.")
            self.list_images()
        except docker.errors.APIError as e:
            self.display_result(f"Error removing image: {e}")

    def tag_image(self, image):
        repo, ok = QInputDialog.getText(self, "Tag Image", "Enter repository name:")
        if ok:
            tag, ok = QInputDialog.getText(self, "Tag Image", "Enter tag name:")
            if ok:
                try:
                    self.docker_client.tag_image(image['id'], repo, tag)
                    self.display_result(f"Image {image['id']} tagged successfully as {repo}:{tag}.")
                except docker.errors.APIError as e:
                    self.display_result(f"Error tagging image: {e}")

    def push_image(self, image):
        repo, ok = QInputDialog.getText(self, "Push Image", "Enter repository name:")
        if ok:
            try:
                result = subprocess.run(["docker", "push", f"{repo}:{image['tags'][0].split(':')[1]}"], capture_output=True, text=True)
                self.display_result(result.stdout)
                if result.stderr:
                    self.display_result(f"Errors:\n{result.stderr}")
            except subprocess.CalledProcessError as e:
                self.display_result(f"Error pushing image: {e}")

    def pull_image(self, image):
        repo, ok = QInputDialog.getText(self, "Pull Image", "Enter repository name:")
        if ok:
            try:
                result = subprocess.run(["docker", "pull", repo], capture_output=True, text=True)
                self.display_result(result.stdout)
                if result.stderr:
                    self.display_result(f"Errors:\n{result.stderr}")
            except subprocess.CalledProcessError as e:
                self.display_result(f"Error pulling image: {e}")

    def inspect_network(self, network):
        details = network.attrs
        self.display_result(f"Details for network {network.name}:\n{details}")

    def remove_network_prompt(self, network):
        reply = QMessageBox.question(
            self, 'Remove Network', 
            f"Are you sure you want to remove the network '{network.name}'?", 
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.remove_network(network)


    def remove_network(self, network):
        try:
            self.docker_client.remove_network(network.id)
            self.display_result(f"Network '{network.name}' removed successfully.")
            self.list_networks() 
        except docker.errors.APIError as e:
            self.display_result(f"Error removing network: {e}")


