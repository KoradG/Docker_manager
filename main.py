import sys
import docker
import subprocess
import os
import tempfile
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import QThread, pyqtSignal
import pyqtgraph as pg
import numpy as np

# Docker client initialization
try:
    client = docker.from_env()
except Exception as e:
    print(f"Error connecting to Docker daemon: {e}")
    sys.exit(1)

# Detect available terminal emulator
def detect_terminal():
    terminals = ["gnome-terminal", "xterm", "konsole", "lxterminal", "mate-terminal", "terminator"]
    for terminal in terminals:
        if subprocess.call(f"type {terminal}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0:
            return terminal
    return None

terminal_emulator = detect_terminal()
if not terminal_emulator:
    print("No supported terminal emulator found. Please install one of the following: gnome-terminal, xterm, konsole, lxterminal, mate-terminal, terminator.")
    sys.exit(1)

class ResourceGraphWidget(QWidget):
    def __init__(self, container_name):
        super().__init__()
        self.container_name = container_name
        self.initUI()

    def initUI(self):
        self.setWindowTitle(f"Resource Usage for {self.container_name}")
        self.setGeometry(100, 100, 800, 600)
        layout = QVBoxLayout()

        # Create plot widgets for CPU, memory, and disk usage
        self.cpu_plot = pg.PlotWidget()
        self.memory_plot = pg.PlotWidget()
        self.disk_plot = pg.PlotWidget()

        layout.addWidget(self.cpu_plot)
        layout.addWidget(self.memory_plot)
        layout.addWidget(self.disk_plot)

        self.setLayout(layout)

        # Initialize plot lines
        self.cpu_curve = self.cpu_plot.plot(pen='r', name='CPU Usage (%)')
        self.memory_curve = self.memory_plot.plot(pen='g', name='Memory Usage (%)')
        self.disk_curve = self.disk_plot.plot(pen='b', name='Disk Usage (%)')

        # Initialize data arrays
        self.cpu_data = []
        self.memory_data = []
        self.disk_data = []

        # Initialize timestamps
        self.timestamps = []

    def update_graph(self, cpu_usage, memory_usage, disk_usage):
        # Append new data
        self.cpu_data.append(cpu_usage)
        self.memory_data.append(memory_usage)
        self.disk_data.append(disk_usage)
        self.timestamps.append(len(self.timestamps) + 1)  # Simple index as time

        # Update the plots
        self.cpu_curve.setData(self.timestamps, self.cpu_data)
        self.memory_curve.setData(self.timestamps, self.memory_data)
        self.disk_curve.setData(self.timestamps, self.disk_data)

        # Set labels
        self.cpu_plot.setLabel('left', 'CPU Usage (%)')
        self.cpu_plot.setLabel('bottom', 'Time')
        self.cpu_plot.addLegend()

        self.memory_plot.setLabel('left', 'Memory Usage (%)')
        self.memory_plot.setLabel('bottom', 'Time')
        self.memory_plot.addLegend()

        self.disk_plot.setLabel('left', 'Disk Usage (%)')
        self.disk_plot.setLabel('bottom', 'Time')
        self.disk_plot.addLegend()

class ResourceMonitorThread(QThread):
    update_graph = pyqtSignal(float, float, float)

    def __init__(self, container):
        super().__init__()
        self.container = container

    def run(self):
        prev_cpu = None
        prev_system = None

        while True:
            try:
                stats = self.container.stats(stream=False)
                cpu_stats = stats['cpu_stats']
                precpu_stats = stats.get('precpu_stats', cpu_stats)  # Fallback to current if pre-stats unavailable

                cpu_total = cpu_stats['cpu_usage']['total_usage']
                cpu_system = cpu_stats['system_cpu_usage']
                precpu_total = precpu_stats['cpu_usage']['total_usage']
                precpu_system = precpu_stats['system_cpu_usage']

                num_cpus = len(cpu_stats['cpu_usage'].get('percpu_usage', [1]))  # Default to 1 if percpu_usage not available

                if prev_cpu is not None and prev_system is not None:
                    cpu_delta = cpu_total - prev_cpu
                    system_delta = cpu_system - prev_system

                    if system_delta > 0 and cpu_delta > 0:
                        cpu_usage = (cpu_delta / system_delta) * num_cpus * 100.0
                    else:
                        cpu_usage = 0.0
                else:
                    cpu_usage = 0.0

                prev_cpu = cpu_total
                prev_system = cpu_system

                memory_usage = (stats['memory_stats']['usage'] / stats['memory_stats']['limit']) * 100
                disk_usage = self.get_disk_usage()  # Replace with actual disk usage logic

                self.update_graph.emit(cpu_usage, memory_usage, disk_usage)
            except KeyError as e:
                print(f"KeyError: {e} - Stats might be incomplete.")
                cpu_usage = 0.0  # Fallback to zero usage if incomplete stats
                self.update_graph.emit(cpu_usage, 0.0, 0.0)
            except docker.errors.APIError as e:
                print(f"APIError: {e}")
            except Exception as e:
                print(f"Exception: {e}")

            self.sleep(1)  # Update every 1 second

    def get_disk_usage(self):
        # Placeholder for disk usage logic, e.g., reading from the filesystem
        return np.random.random() * 100



class DockerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Docker Management")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # Buttons layout
        button_layout = QHBoxLayout()

        # Define buttons
        buttons = [
            ("List Containers", self.list_containers),
            ("Create Container", self.create_container_prompt),
        ]

        for text, func in buttons:
            button = QPushButton(text, self)
            button.clicked.connect(func)
            button_layout.addWidget(button)

        layout.addLayout(button_layout)

        # Result text area
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        self.setLayout(layout)

        # Container window
        self.container_window = None

    def list_containers(self):
        containers = client.containers.list(all=True)
        self.show_containers_table(containers)

    def show_containers_table(self, containers):
        if self.container_window:
            self.container_window.close()

        self.container_window = QWidget()
        self.container_window.setWindowTitle("Containers")
        self.container_window.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        table = QTableWidget()
        table.setRowCount(len(containers))
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(["ID", "Name", "Status", "Start", "Stop", "Remove", "Shell", "Monitor"])
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

        layout.addWidget(table)
        self.container_window.setLayout(layout)
        self.container_window.show()

    def create_action_button(self, text, container, func):
        button = QPushButton(text)
        button.clicked.connect(lambda checked, c=container: func(c))
        return button

    def start_container(self, container):
        try:
            container.start()
            self.display_result(f"Container {container.name} started successfully.")
            self.list_containers()  # Refresh list after starting container
        except docker.errors.APIError as e:
            self.display_result(f"Error occurred: {e}")

    def stop_container(self, container):
        try:
            container.stop()
            self.display_result(f"Container {container.name} stopped successfully.")
            self.list_containers()  # Refresh list after stopping container
        except docker.errors.APIError as e:
            self.display_result(f"Error occurred: {e}")

    def remove_container(self, container):
        try:
            container.remove(force=True)
            self.display_result(f"Container {container.name} removed successfully.")
            self.list_containers()  # Refresh list after removing container
        except docker.errors.APIError as e:
            self.display_result(f"Error occurred: {e}")

    def open_shell(self, container):
        try:
            # Open terminal emulator with a command to follow the logs
            terminal_command = f"{terminal_emulator} -e 'docker logs -f {container.id}'"
            
            # Print command for debugging
            print(f"Executing command: {terminal_command}")

            # Open a new terminal window to follow the logs in real-time
            subprocess.Popen(terminal_command, shell=True)

        except docker.errors.APIError as e:
            self.display_result(f"Error occurred while fetching logs: {e}")
            print(f"APIError: {e}")
        except Exception as e:
            self.display_result(f"Error occurred while opening terminal with logs: {e}")
            print(f"Exception: {e}")


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
        try:
            if not os.path.isdir(dockerfile_path):
                self.display_result(f"Error: {dockerfile_path} is not a valid directory.")
                return

            image, build_logs = client.images.build(path=dockerfile_path, tag="mydockerimage")
            container = client.containers.run(image, detach=True)
            self.display_result(f"Container {container.name} created successfully.")
            self.display_result(f"Container ID: {container.id}")
            self.display_result(f"Container Status: {container.status}")
            self.display_result(f"Container IP Address: {container.attrs['NetworkSettings']['IPAddress']}")
            self.list_containers()  # Refresh list after creating container
        except Exception as e:
            self.display_result(f"Error occurred while creating container: {e}")

    def display_result(self, message):
        self.result_text.append(message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = DockerGUI()
    gui.show()
    sys.exit(app.exec_())
