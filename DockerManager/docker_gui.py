from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QLabel, QDialog,
    QFileDialog, QMessageBox, QFrame, QShortcut, QDialogButtonBox, QProgressBar,
    QProgressDialog, QGroupBox, QSizePolicy, QScrollArea, QMenu
)

from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import QPropertyAnimation, QRect
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import os
import yaml
import subprocess
import docker
from docker.errors import APIError as DockerAPIError

from logs import Logger
from docker_client import get_docker_client
from resource_monitor import ResourceGraphWidget, ResourceMonitorThread
from terminal_utils import terminal_emulator, open_terminal_with_command
from swarm import SwarmManager



class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.setGeometry(150, 150, 400, 300)

        layout = QVBoxLayout()

        help_text = QLabel("Shortcut Keys:\n"
                           "Ctrl+1: Toggle Image Actions\n"
                           "Ctrl+2: Toggle Volume Actions\n"
                           "Ctrl+3: Toggle Network Actions\n"
                           "Ctrl+4: Toggle Other Actions\n")

        layout.addWidget(help_text)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)



class PullImageThread(QThread):
    progress = pyqtSignal(str)  # Signal to update progress

    def __init__(self, client, repository):
        super().__init__()
        self.client = client
        self.repository = repository

    def run(self):
        try:
            self.progress.emit("Starting pull...")
            for chunk in self.client.api.pull(self.repository, stream=True, decode=True):
                if 'status' in chunk:
                    self.progress.emit(chunk['status'])
            self.progress.emit("Pull complete!")
        except docker.errors.APIError as e:
            self.progress.emit(f"API error: {e}")
        except Exception as e:
            self.progress.emit(f"Unexpected error: {e}")



class DockerGui(QWidget):
    def __init__(self):
        super().__init__()
        self.docker_client = docker.from_env() 
        self.logger = Logger()
        self.swarm = SwarmManager(self.logger)

        # Initialize window attributes
        self.container_window = None
        self.image_window = None
        self.network_window = None
        self.volume_window = None
        self.monitor_windows = {}
        self.monitor_thread = None
        self.service_window = None
        self.yaml_output = None

        self.initUi()

    def initUi(self):
        self.setWindowTitle("Docker Manager")
        self.setGeometry(100, 100, 800, 600)

        main_layout = QVBoxLayout()

        # Create a QGroupBox to group the section buttons with padding
        section_group = QGroupBox("Actions")
        section_button_layout = QHBoxLayout()

        # Create frames for each section, which will be collapsible
        self.container_frame = self.create_frame()
        self.volume_frame = self.create_frame()
        self.network_frame = self.create_frame()
        self.other_frame = self.create_frame()

        # Add buttons to control the visibility of each section
        self.container_button = self.create_button("Image Actions", self.container_frame)
        self.volume_button = self.create_button("Volume Actions", self.volume_frame)
        self.network_button = self.create_button("Network Actions", self.network_frame)
        self.other_button = self.create_button("Other Actions", self.other_frame)

        # Add the buttons to the horizontal layout
        section_button_layout.addWidget(self.container_button)
        section_button_layout.addWidget(self.volume_button)
        section_button_layout.addWidget(self.network_button)
        section_button_layout.addWidget(self.other_button)

        # Set the layout for the section group
        section_group.setLayout(section_button_layout)
        main_layout.addWidget(section_group)

        # Populate the frames with their respective buttons and layouts
        self.populate_container_frame(self.container_frame)
        self.populate_volume_frame(self.volume_frame)
        self.populate_network_frame(self.network_frame)
        self.populate_other_frame(self.other_frame)

        # Add the frames to the main layout
        main_layout.addWidget(self.container_frame)
        main_layout.addWidget(self.volume_frame)
        main_layout.addWidget(self.network_frame)
        main_layout.addWidget(self.other_frame)

        # Add QTextEdit for output messages
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        main_layout.addWidget(self.result_text)

        # Add Help button to the bottom right
        self.help_button = QPushButton("Help", self)
        self.help_button.clicked.connect(self.show_help_dialog)
        self.help_button.setFixedSize(100, 30)

        # Make sure the Help button is aligned to the bottom right
        help_button_layout = QHBoxLayout()
        help_button_layout.addStretch()
        help_button_layout.addWidget(self.help_button)
        main_layout.addLayout(help_button_layout)

        self.setLayout(main_layout)

        # Add hotkeys for existing buttons
        self.add_shortcuts()

    def create_frame(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setVisible(False)
        return frame

    def create_button(self, text, associated_frame):
        button = QPushButton(text, self)
        button.setCheckable(True)
        button.clicked.connect(lambda: self.toggle_frame(associated_frame, button))
        button.setStyleSheet("""
            QPushButton {
                padding: 10px;
                background-color: #3498db;
                color: white;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #2980b9;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        return button

    def toggle_frame(self, frame, button):
        if frame.isVisible():
            self.animate_frame(frame, False)
            button.setChecked(False)
        else:
            self.animate_frame(frame, True)
            button.setChecked(True)

    def animate_frame(self, frame, expanding):
        animation = QPropertyAnimation(frame, b"geometry")
        start_geometry = frame.geometry()
        if expanding:
            end_geometry = QRect(start_geometry.x(), start_geometry.y(), start_geometry.width(), 200)
        else:
            end_geometry = QRect(start_geometry.x(), start_geometry.y(), start_geometry.width(), 0)

        animation.setDuration(300)
        animation.setStartValue(start_geometry)
        animation.setEndValue(end_geometry)
        animation.start()

        frame.setVisible(True if expanding else False)


    def add_shortcuts(self):
        # Define and add hotkeys for existing buttons
        QShortcut(QKeySequence("Ctrl+1"), self).activated.connect(lambda: self.container_button.click())
        QShortcut(QKeySequence("Ctrl+2"), self).activated.connect(lambda: self.volume_button.click())
        QShortcut(QKeySequence("Ctrl+3"), self).activated.connect(lambda: self.network_button.click())
        QShortcut(QKeySequence("Ctrl+4"), self).activated.connect(lambda: self.other_button.click())

    def show_help_dialog(self):
        help_dialog = HelpDialog(self)
        help_dialog.exec_()

    def toggle_frame(self, frame, button):
        frame.setVisible(not frame.isVisible())
        button.setChecked(frame.isVisible())

    def populate_container_frame(self, frame):
        layout = QHBoxLayout()
        layout.setSpacing(10)  # Add spacing between buttons

        container_buttons = [
            ("List Containers", self.list_containers),
            ("Create Container", self.create_container_prompt),
            ("List Images", self.list_images),
            ("Pull Image", self.pull_image),
        ]

        for text, func in container_buttons:
            button = self.create_styled_button(text, func)
            layout.addWidget(button)

        layout.addStretch()  # Pushes the buttons to the left and leaves space at the right
        frame.setLayout(layout)

    def populate_volume_frame(self, frame):
        layout = QHBoxLayout()
        layout.setSpacing(10)  # Add spacing between buttons

        volume_buttons = [
            ("List Volumes", self.list_volumes),
            ("Create Volume", self.create_volume_prompt),
            ("Prune Unused Volumes", self.prune_volumes),
        ]

        for text, func in volume_buttons:
            button = self.create_styled_button(text, func)
            layout.addWidget(button)

        layout.addStretch()  # Pushes the buttons to the left and leaves space at the right
        frame.setLayout(layout)

    def populate_network_frame(self, frame):
        layout = QHBoxLayout()
        layout.setSpacing(10)  # Add spacing between buttons

        network_buttons = [
            ("List Networks", self.list_networks),
            ("Create Network", self.create_network_prompt),
        ]

        for text, func in network_buttons:
            button = self.create_styled_button(text, func)
            layout.addWidget(button)

        layout.addStretch()  # Pushes the buttons to the left and leaves space at the right
        frame.setLayout(layout)

    def populate_other_frame(self, frame):
        layout = QHBoxLayout()
        layout.setSpacing(10)  # Add spacing between buttons

        other_buttons = [
            ("Create Compose File", self.create_compose_form),
            ("Docker Swarm", self.show_swarm_dialog),
        ]

        for text, func in other_buttons:
            button = self.create_styled_button(text, func)
            layout.addWidget(button)

        layout.addStretch()  # Pushes the buttons to the left and leaves space at the right
        frame.setLayout(layout)

    def create_styled_button(self, text, func):
        button = QPushButton(text, self)
        button.clicked.connect(func)
        button.setStyleSheet("""
            QPushButton {
                padding: 10px;
                background-color: #2ecc71;
                color: white;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        return button



    def display_result(self, result):
        self.result_text.append(result)

    def list_containers(self):
        try:
            self.logger.log_info("Listing all containers.")
            containers = self.docker_client.containers.list(all=True)
            self.show_containers_table(containers)
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error listing containers: {e}")


    def show_containers_table(self, containers):
        if self.container_window:
            self.container_window.close()

        self.container_window = QWidget()
        self.container_window.setWindowTitle("Containers")
        self.container_window.setGeometry(100, 100, 1000, 600)  # Adjusted size for better fit

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)  # Add padding around the table

        table = QTableWidget()
        table.setRowCount(len(containers))
        table.setColumnCount(6)  # Columns: ID, Name, Status, Manage, Inspect, Stats
        table.setHorizontalHeaderLabels([
            "ID", "Name", "Status", "Manage", "Inspect", "Stats"
        ])

        # Customize header
        header = table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #3498db;
                color: white;
                padding: 5px;
                border: 1px solid #2980b9;
            }
        """)
        header.setSectionResizeMode(QHeaderView.Stretch)  # Let columns stretch to fit the window
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        
        table.verticalHeader().setDefaultSectionSize(40)  # Adjust row height

        # Populate the table with data and grouped action buttons
        for row, container in enumerate(containers):
            table.setItem(row, 0, QTableWidgetItem(container.id))
            table.setItem(row, 1, QTableWidgetItem(container.name))
            table.setItem(row, 2, QTableWidgetItem(container.status))

            # Create "Manage" button with related actions
            manage_button = QPushButton("Manage")
            manage_menu = QMenu(manage_button)
            manage_menu.addAction("Start", lambda c=container: self.start_container(c))
            manage_menu.addAction("Stop", lambda c=container: self.stop_container(c))
            manage_menu.addAction("Pause", lambda c=container: self.pause_container(c))
            manage_menu.addAction("Unpause", lambda c=container: self.unpause_container(c))
            manage_menu.addAction("Remove", lambda c=container: self.remove_container(c))
            manage_button.setMenu(manage_menu)
            table.setCellWidget(row, 3, manage_button)

            # Create "Inspect" button with related actions
            inspect_button = QPushButton("Inspect")
            inspect_menu = QMenu(inspect_button)
            inspect_menu.addAction("Logs", lambda c=container: self.open_log(c))
            inspect_menu.addAction("Shell", lambda c=container: self.open_shell(c))
            inspect_menu.addAction("Inspect", lambda c=container: self.inspect_container(c))
            inspect_button.setMenu(inspect_menu)
            table.setCellWidget(row, 4, inspect_button)

            # Create "Stats" button with related actions
            stats_button = QPushButton("Stats")
            stats_menu = QMenu(stats_button)
            stats_menu.addAction("Stats", lambda c=container: self.show_stats(c))
            stats_menu.addAction("Monitor", lambda c=container: self.open_monitor(c))
            stats_button.setMenu(stats_menu)
            table.setCellWidget(row, 5, stats_button)

        layout.addWidget(table)
        self.container_window.setLayout(layout)
        self.container_window.show()
        
    def list_images(self):
        try:
            self.logger.log_info("Listing all images.")
            images = self.docker_client.images.list()
            self.show_images_table(images)
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error listing images: {e}")

    def show_images_table(self, images):
        if self.image_window:
            self.image_window.close()

        self.image_window = QWidget()
        self.image_window.setWindowTitle("Images")
        self.image_window.setGeometry(100, 100, 1000, 600)  # Adjusted size for better fit

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setRowCount(len(images))
        table.setColumnCount(7)  # Adjusted to 7 columns
        table.setHorizontalHeaderLabels([
            "ID", "Tags", "Remove", "Tag", "Push", "Run", "Stop"
        ])  # Updated header labels
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Apply styling to the table
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(40)  # Adjust row height

        for row, img in enumerate(images):
            image_id = img.id
            tags = img.tags if img.tags else []

            table.setItem(row, 0, QTableWidgetItem(image_id))  # ID
            table.setItem(row, 1, QTableWidgetItem(", ".join(tags)))  # Tags

            # Create and style buttons
            button_style = """
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1c598a;
                }
            """

            remove_button = QPushButton("Remove")
            remove_button.setStyleSheet(button_style)
            remove_button.clicked.connect(lambda _, i=img: self.remove_image(i))
            table.setCellWidget(row, 2, remove_button)  # Remove

            tag_button = QPushButton("Tag")
            tag_button.setStyleSheet(button_style)
            tag_button.clicked.connect(lambda _, i=img: self.tag_image(i))
            table.setCellWidget(row, 3, tag_button)  # Tag

            push_button = QPushButton("Push")
            push_button.setStyleSheet(button_style)
            push_button.clicked.connect(lambda _, i=img: self.push_image(i))
            table.setCellWidget(row, 4, push_button)  # Push

            run_button = QPushButton("Run")
            run_button.setStyleSheet(button_style)
            run_button.clicked.connect(lambda _, i=img: self.run_image(i))
            table.setCellWidget(row, 5, run_button)  # Run

            stop_button = QPushButton("Stop")
            stop_button.setStyleSheet(button_style)
            stop_button.clicked.connect(lambda _, i=img: self.stop_container_for_image(i))
            table.setCellWidget(row, 6, stop_button)  # Stop

        layout.addWidget(table)
        self.image_window.setLayout(layout)
        self.image_window.show()

    def run_image(self, image):
        try:
            # Start a container from the image
            container = self.docker_client.containers.run(
                image.id,  # Use the image ID to start the container
                detach=True,  # Run container in detached mode
                tty=True  # Allocate a pseudo-TTY
            )

            self.logger.log_info(f"Container started from image '{image.id}'. Container ID: {container.id}")

            # Open a shell in a terminal to the running container
            self.open_shell(container)
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error running image '{image.id}': {e}")



    def stop_container_for_image(self, image):
        try:
            # Get the list of running containers
            containers = self.docker_client.containers.list()
            
            # Find the container running the given image
            container_to_stop = None
            for container in containers:
                if container.image.id == image.id:
                    container_to_stop = container
                    break
            
            if container_to_stop:
                container_to_stop.stop()
                self.logger.log_info(f"Container with ID '{container_to_stop.id}' stopped successfully.")
            else:
                self.logger.log_warning(f"No running container found for image '{image.id}'.")

        except docker.errors.APIError as e:
            self.logger.log_error(f"Error stopping container for image '{image.id}': {e}")



    def list_networks(self):
        try:
            self.logger.log_info("Listing all networks.")
            networks = self.docker_client.networks.list()
            self.show_networks_table(networks)
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error listing networks: {e}")

    def show_networks_table(self, networks):
        if self.network_window:
            self.network_window.close()

        self.network_window = QWidget()
        self.network_window.setWindowTitle("Networks")
        self.network_window.setGeometry(100, 100, 800, 600)  # Adjusted size for better fit

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setRowCount(len(networks))
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Name", "ID", "Driver", "Scope", "Inspect", "Remove"
        ])  # Updated header labels
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Apply styling to the table
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(40)  # Adjust row height

        # Button styling
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c598a;
            }
        """

        for row, network in enumerate(networks):
            table.setItem(row, 0, QTableWidgetItem(network.name))  # Name
            table.setItem(row, 1, QTableWidgetItem(network.id))  # ID
            table.setItem(row, 2, QTableWidgetItem(network.attrs.get('Driver', '')))  # Driver
            table.setItem(row, 3, QTableWidgetItem(network.attrs.get('Scope', '')))  # Scope

            # Create and style buttons
            inspect_button = QPushButton("Inspect")
            inspect_button.setStyleSheet(button_style)
            inspect_button.clicked.connect(lambda _, n=network: self.inspect_network(n))
            table.setCellWidget(row, 4, inspect_button)  # Inspect

            remove_button = QPushButton("Remove")
            remove_button.setStyleSheet(button_style)
            remove_button.clicked.connect(lambda _, n=network: self.remove_network_prompt(n))
            table.setCellWidget(row, 5, remove_button)  # Remove

        layout.addWidget(table)
        self.network_window.setLayout(layout)
        self.network_window.show()

    def list_volumes(self):
        try:
            self.logger.log_info("Listing all volumes.")
            volumes = self.docker_client.volumes.list()
            self.show_volumes_table(volumes)
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error listing volumes: {e}")

    def show_volumes_table(self, volumes):
        if self.volume_window:
            self.volume_window.close()

        self.volume_window = QWidget()
        self.volume_window.setWindowTitle("Volumes")
        self.volume_window.setGeometry(100, 100, 800, 600)  # Adjusted size for better fit

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setRowCount(len(volumes))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            "Name", "ID", "Driver", "Remove"
        ])  # Updated header labels
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Apply styling to the table
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(40)  # Adjust row height

        # Button styling
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c598a;
            }
        """

        for row, volume in enumerate(volumes):
            table.setItem(row, 0, QTableWidgetItem(volume.name))  # Name
            table.setItem(row, 1, QTableWidgetItem(volume.id))  # ID
            table.setItem(row, 2, QTableWidgetItem(volume.attrs.get('Driver', '')))  # Driver

            # Create and style button
            remove_button = QPushButton("Remove")
            remove_button.setStyleSheet(button_style)
            remove_button.clicked.connect(lambda _, v=volume: self.remove_volume_prompt(v))
            table.setCellWidget(row, 3, remove_button)  # Remove

        layout.addWidget(table)
        self.volume_window.setLayout(layout)
        self.volume_window.show()

    def prune_volumes(self):
        try:
            self.logger.log_info("Pruning unused volumes.")
            result = self.docker_client.volumes.prune()
            self.logger.log_info(f"Pruned volumes: {result}")
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error pruning volumes: {e}")


    def create_container_prompt(self):
        try:
            self.logger.log_info("Prompting user to create a new container.")

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
                    self.logger.log_error("Container name and Dockerfile path are required to create a container.")

        except Exception as e:
            self.logger.log_error(f"Error creating container: {e}")

    def browse_dockerfile(self, dockerfile_input):
        # Open file dialog to select Dockerfile path
        dockerfile_path, _ = QFileDialog.getOpenFileName(self, "Select Dockerfile", "", "Dockerfile (*.Dockerfile);;All Files (*)")
        if dockerfile_path:
            dockerfile_input.setText(dockerfile_path)

    def create_container_from_dockerfile(self, container_name, dockerfile_path, flags=None):
        try:
            self.logger.log_info(f"Building image from Dockerfile at: {dockerfile_path}")

            # Extract directory and Dockerfile filename
            dockerfile_dir = os.path.dirname(dockerfile_path)
            dockerfile_name = os.path.basename(dockerfile_path)

            # Build the image from Dockerfile
            try:
                image, build_logs = self.docker_client.images.build(
                    path=dockerfile_dir, dockerfile=dockerfile_name, tag=container_name
                )
                for log in build_logs:
                    self.logger.log_info(log.get("stream", "").strip())  # Log the build output
                self.logger.log_info(f"Image '{container_name}' built successfully from Dockerfile.")
            except docker.errors.BuildError as e:
                self.logger.log_error(f"Failed to build image from Dockerfile: {e}")
                return

            # Prepare container arguments
            run_args = {'detach': True, 'name': container_name}

            if flags:
                # Process flags and add to the arguments as needed
                self.logger.log_info(f"Running container with flags: {flags}")
                # Example: split the flags string by spaces
                flag_list = flags.split()
                run_args.update({'command': flag_list})

            # Run the container from the built image
            self.docker_client.containers.run(container_name, **run_args)
            self.logger.log_info(f"Container '{container_name}' created successfully.")

        except docker.errors.APIError as e:
            self.logger.log_error(f"Error creating container: {e}")


    def create_container(self, container_name, image_name, dockerfile_path=None, flags=None):
        try:
            self.logger.log_info(f"Creating container with name: {container_name} and image: {image_name}")

            # If a Dockerfile is provided, build the image first
            if dockerfile_path:
                self.logger.log_info(f"Building image from Dockerfile at: {dockerfile_path}")

                # Use Docker's SDK to build the image from the Dockerfile
                try:
                    image, self.logger = self.docker_client.images.build(path=dockerfile_path, tag=image_name)
                    for log in self.logger:
                        self.logger.log_info(log.get("stream", "").strip())  # Log the build output
                    self.logger.log_info(f"Image '{image_name}' built successfully from Dockerfile.")
                except docker.errors.BuildError as e:
                    self.logger.log_error(f"Failed to build image from Dockerfile: {e}")
                    return

            # Prepare container arguments
            run_args = {'detach': True, 'name': container_name}

            if flags:
                # Process flags and add to the arguments as needed
                self.logger.log_info(f"Running container with flags: {flags}")
                # Example: split the flags string by spaces
                flag_list = flags.split()
                run_args.update({'command': flag_list})

            self.logger.log_info(f"Container '{container_name}' created successfully.")

        except docker.errors.APIError as e:
            self.logger.log_error(f"Error creating container: {e}")


    def deploy_compose_prompt(self):
        try:
            self.logger.log_info("Prompting user to deploy a Docker Compose file.")
            file_path, _ = QFileDialog.getOpenFileName(self, "Open Docker Compose File", "", "YAML Files (*.yml *.yaml)")
            if file_path:
                self.deploy_compose(file_path)
        except Exception as e:
            self.logger.log_error(f"Error deploying compose file: {e}")

    def create_network_prompt(self):
        try:
            self.logger.log_info("Prompting user to create a new network.")
            network_name, ok = QInputDialog.getText(self, "Create Network", "Network name:")
            if ok and network_name:
                self.create_network(network_name)
        except Exception as e:
            self.logger.log_error(f"Error creating network: {e}")

    def create_network(self, network_name):
        try:
            self.logger.log_info(f"Creating network with name: {network_name}")
            self.docker_client.networks.create(name=network_name, driver="bridge")
            self.logger.log_info(f"Network '{network_name}' created successfully.")
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error creating network: {e}")

    def create_volume_prompt(self):
        try:
            self.logger.log_info("Prompting user to create a new volume.")
            volume_name, ok = QInputDialog.getText(self, "Create Volume", "Volume name:")
            if ok and volume_name:
                self.create_volume(volume_name)
        except Exception as e:
            self.logger.log_error(f"Error creating volume: {e}")

    def create_volume(self, volume_name):
        try:
            self.logger.log_info(f"Creating volume with name: {volume_name}")
            self.docker_client.volumes.create(name=volume_name)
            self.logger.log_info(f"Volume '{volume_name}' created successfully.")
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error creating volume: {e}")


    def start_container(self, container):
        try:
            container.start()
            self.logger.log_info(f"Container '{container.id}' started.")
            self.display_result(f"Container '{container.id}' started.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error starting container: {e}")

    def stop_container(self, container):
        try:
            container.stop()
            self.logger.log_info(f"Container '{container.id}' stopped.")
            self.display_result(f"Container '{container.id}' stopped.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error stopping container: {e}")

    def pause_container(self, container):
        try:
            # Check if the container is already paused or not running
            if container.status != "running":
                self.logger.log_info(f"Container '{container.id}' is not running, cannot pause.")
                self.display_result(f"Container '{container.id}' is not running, cannot pause.")
                return

            container.pause()  # Attempt to pause the container
            self.logger.log_info(f"Container '{container.id}' paused.")
            self.display_result(f"Container '{container.id}' paused.")
            self.list_containers()

        except docker.errors.APIError as e:
            # Log the full details of the error
            self.logger.log_error(f"Error pausing container: {e.explanation}")
            self.display_result(f"Error pausing container: {e.explanation}")

        except Exception as e:
            # Catch any other unforeseen errors
            self.logger.log_error(f"Unexpected error: {e}")
            self.display_result(f"Unexpected error: {e}")


    def unpause_container(self, container):
        try:
            # Check if the container is paused before unpausing
            if container.status != 'paused':
                self.logger.log_info(f"Container '{container.id}' is not paused, cannot unpause.")
                self.display_result(f"Container '{container.id}' is not paused, cannot unpause.")
                return

            container.unpause()
            self.logger.log_info(f"Container '{container.id}' unpaused.")
            self.display_result(f"Container '{container.id}' unpaused.")
            self.list_containers()
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error unpausing container: {e}")


    def remove_container(self, container):
        try:
            self.logger.log_info(f"Removing container with ID: {container.id}")
            container.remove(force=True)
            self.logger.log_info(f"Container '{container.name}' removed successfully.")
            self.display_result(f"Container '{container.name}' removed successfully.")
            self.list_containers() 
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error removing container: {e}")



    def open_log(self, container):
        try:
            # Fetch container logs, stream if needed
            log = container.logs(stream=False).decode('utf-8')

            # Display the fetched logs in the UI
            if log:
                self.display_result(log)
            else:
                self.logger.log_info(f"No logs available for container '{container.name}'.")

        except docker.errors.APIError as e:
            self.logger.log_error(f"APIError fetching logs for container '{container.name}': {e}")
        except Exception as e:
            self.logger.log_error(f"Unexpected error fetching logs for container '{container.name}': {e}")


    def open_shell(self, container):
        try:
            self.logger.log_info(f"Opening shell for container with ID: {container.id}")
            command = f"docker exec -it {container.id} /bin/bash"
            open_terminal_with_command(command)

        except Exception as e:
            self.logger.log_error(f"Error opening shell for container: {e}")

    def remove_image(self, image):
        try:
            self.logger.log_info(f"Removing image with ID: {image.id}")
            self.display_result(f"Removing image with ID: {image.id}")
            self.docker_client.images.remove(image.id, force=True)
            self.logger.log_info(f"Image '{image.id}' removed successfully.")
            self.display_result(f"Image '{image.id}' removed successfully.")
            self.list_images()
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error removing image: {e}")

    def tag_image(self, image):
        try:
            self.logger.log_info(f"Prompting user to tag image with ID: {image.id}")
            tag, ok = QInputDialog.getText(self, "Tag Image", "New tag:")
            if ok and tag:
                self.logger.log_info(f"Tagging image with ID: {image.id} with tag: {tag}")
                self.display_result(f"Tagging image with ID: {image.id} with tag: {tag}")
                image.tag(tag)
                self.logger.log_info(f"Image '{image.id}' tagged with '{tag}' successfully.")
                self.display_result(f"Image '{image.id}' tagged with '{tag}' successfully.")
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error tagging image: {e}")

    def push_image(self, image):
        try:
            self.logger.log_info(f"Prompting user to push image with ID: {image.id}")
            self.display_result(f"Prompting user to push image with ID: {image.id}")
            repository, ok = QInputDialog.getText(self, "Push Image", "Repository:")
            if ok and repository:
                self.logger.log_info(f"Pushing image with ID: {image.id} to repository: {repository}")
                self.display_result(f"Pushing image with ID: {image.id} to repository: {repository}")
                self.docker_client.images.push(repository)
                self.logger.log_info(f"Image '{image.id}' pushed to repository '{repository}' successfully.")
                self.display_result(f"Image '{image.id}' pushed to repository '{repository}' successfully.")
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error pushing image: {e}")

    def pull_image(self):
        try:
            # Prompt user for repository name
            repository, ok = QInputDialog.getText(self, "Pull Image", "Enter image name (e.g., 'ubuntu' or 'ubuntu:latest'):")
            
            if not ok or not repository:
                self.display_result("Input Error", "No repository name provided.")
                self.logger.log_error("Input Error", "No repository name provided.")
                return

            # Create and show the progress dialog
            progress_dialog = QProgressDialog("Pulling image...", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Pulling Image")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            
            
            # Thread to handle Docker image pulling
            self.pull_thread = PullImageThread(self.docker_client, repository)
            self.pull_thread.progress.connect(lambda message: self.update_progress(message, progress_dialog))
            self.pull_thread.finished.connect(progress_dialog.close)
            self.pull_thread.start()

        except Exception as e:
            self.display_result("Error", f"An error occurred: {e}")
            self.logger.log_error("Error", f"An error occurred: {e}")

    def update_progress(self, message, progress_dialog):
        if "status" in message:
            # Update progress dialog with status message
            progress_dialog.setLabelText(f"Status: {message}")
        if "complete" in message.lower():
            progress_dialog.setValue(100)
            self.display_result("Done!")
        elif "starting" in message.lower():
            progress_dialog.setValue(0)
            self.display_result(f"Pulling ...")
        # Allow the progress dialog to be canceled
        if progress_dialog.wasCanceled():
            self.pull_thread.terminate()



    def inspect_container(self, container):
        try:
            self.logger.log_info(f"Inspecting container with ID: {container.id}")
            info = container.attrs
            self.display_result(f"Inspecting container {container.id}:\n{info}")
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error inspecting container: {e}")

    def show_stats(self, container):
        try:
            self.logger.log_info(f"Showing stats for container with ID: {container.id}")
            stats = container.stats(stream=False)
            self.display_result(f"Stats for container {container.id}:\n{stats}")
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error showing stats for container: {e}")

    def open_monitor(self, container):
        try:
            container_id = container.id

            # Check if the container is running
            if container.status != 'running':
                self.logger.log_error(f"Cannot open resource monitor: Container {container_id} is not running.")
                self.display_result(f"Cannot open resource monitor: Container {container_id} is not running.")
                return

            self.logger.log_info(f"Opening resource monitor for container: {container_id}")

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
            self.logger.log_error(f"Error opening resource monitor: {e}")



    def inspect_network(self, network):
        try:
            self.logger.log_info(f"Inspecting network with ID: {network.id}")
            info = network.attrs
            self.display_result(f"Inspecting network {network.id}:\n{info}")
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error inspecting network: {e}")

    def remove_network_prompt(self, network):
        try:
            self.logger.log_info(f"Prompting user to remove network with ID: {network.id}")
            reply = QMessageBox.question(self, 'Remove Network',
                                         f"Are you sure you want to remove network '{network.name}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove_network(network)
        except Exception as e:
            self.logger.log_error(f"Error prompting network removal: {e}")

    def remove_network(self, network):
        try:
            self.logger.log_info(f"Removing network with ID: {network.id}")
            network.remove()
            self.logger.log_info(f"Network '{network.id}' removed successfully.")
            self.list_networks()
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error removing network: {e}")

    def remove_volume_prompt(self, volume):
        try:
            self.logger.log_info(f"Prompting user to remove volume with ID: {volume.id}")
            reply = QMessageBox.question(self, 'Remove Volume',
                                         f"Are you sure you want to remove volume '{volume.name}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove_volume(volume)
        except Exception as e:
            self.logger.log_error(f"Error prompting volume removal: {e}")

    def remove_volume(self, volume):
        try:
            self.logger.log_info(f"Removing volume with ID: {volume.id}")
            self.docker_client.volumes.get(volume.id).remove()
            self.logger.log_info(f"Volume '{volume.id}' removed successfully.")
            self.list_volumes()
        except docker.errors.APIError as e:
            self.logger.log_error(f"Error removing volume: {e}")


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
                "Service Name", "Status", "Start", "Stop", "View self.logger"
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

                # View self.logger Button
                view_self.logger_button = QPushButton("View self.logger")
                view_self.logger_button.clicked.connect(lambda _, s=name: self.view_service_self.logger(s))
                table.setCellWidget(row, 4, view_self.logger_button)

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

        # Replicas input
        self.replicas_input = QLineEdit()
        layout.addWidget(QLabel("Replicas (e.g., 1, 3):"))
        layout.addWidget(self.replicas_input)

        # YAML File Location input (optional)
        self.yaml_location_input = QLineEdit()
        layout.addWidget(QLabel("YAML File Location (optional):"))
        layout.addWidget(self.yaml_location_input)

        # Button to generate YAML
        generate_button = QPushButton("Generate YAML")
        generate_button.clicked.connect(self.generate_full_docker_compose_yaml)
        layout.addWidget(generate_button)

        # Output area for YAML preview
        self.yaml_output = QTextEdit()  # Initialize QTextEdit
        self.yaml_output.setReadOnly(True)
        layout.addWidget(QLabel("Generated YAML:"))
        layout.addWidget(self.yaml_output)

        # Button to deploy the generated YAML
        deploy_button = QPushButton("Deploy Generated YAML")
        deploy_button.clicked.connect(lambda: self.save_and_deploy_yaml())
        layout.addWidget(deploy_button)

        # Button to import and deploy an existing YAML
        import_button = QPushButton("Import and Deploy YAML")
        import_button.clicked.connect(self.import_and_deploy_yaml)
        layout.addWidget(import_button)

        self.compose_window.setLayout(layout)
        self.compose_window.show()


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


    def import_and_deploy_yaml(self):
        """
        Opens a file dialog to select a YAML file and deploys it using Docker Compose.
        """
        # Open file dialog to select a YAML file
        file_path, _ = QFileDialog.getOpenFileName(self.compose_window, "Import Compose File", "", "YAML Files (*.yaml)")

        if file_path:
            try:
                # Deploy the selected YAML file
                self.deploy_compose(file_path)
            except Exception as e:
                self.yaml_output.setPlainText(f"Error importing or deploying Docker Compose file: {str(e)}")


    def deploy_compose(self, file_path):
        """
        Deploys the provided Docker Compose YAML file.
        """
        try:
            self.logger.log_info(f"Deploying Docker Compose file: {file_path}")
            result = subprocess.run(["docker-compose", "-f", file_path, "up", "-d"], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.log_info(f"Successfully deployed Docker Compose file: {file_path}")
            else:
                self.logger.log_error(f"Failed to deploy Docker Compose file: {result.stderr}")
        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Error deploying Docker Compose file: {e}")


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

    def show_swarm_dialog(self):
        """
        Show the Docker Swarm dialog.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Docker Swarm")

        layout = QVBoxLayout(dialog)

        # Initialize Swarm button
        init_swarm_button = QPushButton("Initialize Swarm", dialog)
        init_swarm_button.clicked.connect(self.initialize_swarm)
        layout.addWidget(init_swarm_button)

        # Deploy Service button
        deploy_service_button = QPushButton("Deploy Service", dialog)
        deploy_service_button.clicked.connect(self.deploy_service_prompt)
        layout.addWidget(deploy_service_button)

        # Scale Service button
        scale_service_button = QPushButton("Scale Service", dialog)
        scale_service_button.clicked.connect(self.scale_service_prompt)
        layout.addWidget(scale_service_button)

        # View Nodes button
        view_nodes_button = QPushButton("View Nodes", dialog)
        view_nodes_button.clicked.connect(self.view_nodes)
        layout.addWidget(view_nodes_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def initialize_swarm(self):
        """
        Initialize Docker Swarm.
        """
        result = self.swarm.initialize_swarm()
        self.display_result(result)

    def deploy_service_prompt(self):
        """
        Show the dialog to deploy a Docker service.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Deploy Service")
        layout = QVBoxLayout(dialog)
        
        # Service Name Input
        service_name_label = QLabel("Service Name:")
        service_name_input = QLineEdit(dialog)
        layout.addWidget(service_name_label)
        layout.addWidget(service_name_input)

        # Image Name Input
        image_name_label = QLabel("Image Name:")
        image_name_input = QLineEdit(dialog)
        layout.addWidget(image_name_label)
        layout.addWidget(image_name_input)

        # OK and Cancel buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("Deploy", dialog)
        cancel_button = QPushButton("Cancel", dialog)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        ok_button.clicked.connect(lambda: self.deploy_service(service_name_input.text(), image_name_input.text(), dialog))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

    def deploy_service(self, service_name, image_name, dialog):
        """
        Deploy a Docker service.
        """
        result = self.swarm.deploy_service(service_name, image_name)
        self.display_result(result)
        if "Error" not in result:
            dialog.accept()
        else:
            dialog.reject()

    def scale_service_prompt(self):
        """
        Show the dialog to scale a Docker service.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Scale Service")
        layout = QVBoxLayout(dialog)
        
        # Service Name Input
        service_name_label = QLabel("Service Name:")
        service_name_input = QLineEdit(dialog)
        layout.addWidget(service_name_label)
        layout.addWidget(service_name_input)

        # Replicas Input
        replicas_label = QLabel("Number of Replicas:")
        replicas_input = QLineEdit(dialog)
        layout.addWidget(replicas_label)
        layout.addWidget(replicas_input)

        # OK and Cancel buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("Scale", dialog)
        cancel_button = QPushButton("Cancel", dialog)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        ok_button.clicked.connect(lambda: self.scale_service(service_name_input.text(), replicas_input.text(), dialog))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

    def scale_service(self, service_name, replicas, dialog):
        """
        Scale a Docker service.
        """
        result = self.swarm.scale_service(service_name, replicas)
        self.display_result(result)
        if "Error" not in result:
            dialog.accept()
        else:
            dialog.reject()

    def view_nodes(self):
        """
        View the nodes in Docker Swarm.
        """
        result = self.swarm.view_nodes()
        self.display_result(result)