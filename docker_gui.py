from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView
from docker_client import get_docker_client
from resource_monitor import ResourceGraphWidget, ResourceMonitorThread
from terminal_utils import terminal_emulator
import docker
import sys
import subprocess

class DockerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.docker_client = get_docker_client()  # Use the DockerClient instance
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

        self.container_window = None

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
        self.container_window.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        table = QTableWidget()
        table.setRowCount(len(containers))
        table.setColumnCount(9)  # Update column count
        table.setHorizontalHeaderLabels(["ID", "Name", "Status", "Start", "Stop", "Remove", "Shell", "Monitor", "Logs"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for row, container in enumerate(containers):
            table.setItem(row, 0, QTableWidgetItem(container.id))
            table.setItem(row, 1, QTableWidgetItem(container.name))
            table.setItem(row, 2, QTableWidgetItem(container.status))
            table.setCellWidget(row, 3, self.create_action_button("Start", container, self.start_container))
            table.setCellWidget(row, 4, self.create_action_button("Stop", container, self.stop_container))
            table.setCellWidget(row, 5, self.create_action_button("Remove", container, self.remove_container))
            table.setCellWidget(row, 6, self.create_action_button("Shell", container, self.open_shell))
            table.setCellWidget(row, 7, self.create_action_button("Monitor", container, self.open_monitor))
            table.setCellWidget(row, 8, self.create_action_button("Logs", container, self.open_logs))  # Add Logs button

        layout.addWidget(table)
        self.container_window.setLayout(layout)
        self.container_window.show()

    def create_action_button(self, text, container, func):
        button = QPushButton(text)
        button.clicked.connect(lambda checked, c=container: func(c))
        return button

    def start_container(self, container):
        updated_container = self.docker_client.perform_container_action(container, container.start, "started")
        if updated_container:
            self.list_containers()  # Refresh status

    def stop_container(self, container):
        updated_container = self.docker_client.perform_container_action(container, container.stop, "stopped")
        if updated_container:
            self.list_containers()  # Refresh status

    def remove_container(self, container):
        updated_container = self.docker_client.perform_container_action(container, lambda: container.remove(force=True), "removed")
        if updated_container:
            self.list_containers()  # Refresh status

    def open_shell(self, container):
        try:
            terminal_command = f"{terminal_emulator} -e 'docker exec -it {container.id} /bin/bash'"
            subprocess.Popen(terminal_command, shell=True)
        except Exception as e:
            self.display_result(f"Error occurred while opening terminal with shell: {e}")

    def open_logs(self, container):
        try:
            terminal_command = f"{terminal_emulator} -e 'docker logs -f {container.id}'"
            subprocess.Popen(terminal_command, shell=True)
        except Exception as e:
            self.display_result(f"Error occurred while opening terminal with logs: {e}")

    def open_monitor(self, container):
        self.monitor_window = ResourceGraphWidget(container.name)
        self.monitor_window.show()

        self.monitor_thread = ResourceMonitorThread(container)
        self.monitor_thread.update_graph.connect(self.monitor_window.update_graph)
        self.monitor_thread.start()

    def create_container_prompt(self):
        dockerfile_path, ok = QInputDialog.getText(self, "Create Container", "Enter path to Dockerfile directory:")
        if ok and dockerfile_path:
            self.create_container_from_dockerfile(dockerfile_path)

    def create_container_from_dockerfile(self, dockerfile_path):
        container = self.docker_client.create_container_from_dockerfile(dockerfile_path)
        if container:
            self.display_result(f"Container {container.name} created successfully.")
            self.display_result(f"Container ID: {container.id}")
            self.display_result(f"Container Status: {container.status}")
            self.display_result(f"Container IP Address: {container.attrs['NetworkSettings']['IPAddress']}")
            self.list_containers()

    def deploy_compose_prompt(self):
        compose_file_path, ok = QInputDialog.getText(self, "Deploy Compose File", "Enter path to Docker Compose file:")
        if ok and compose_file_path:
            self.docker_client.deploy_compose_file(compose_file_path)

    def display_result(self, message):
        self.result_text.append(message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = DockerGUI()
    gui.show()
    sys.exit(app.exec_())
