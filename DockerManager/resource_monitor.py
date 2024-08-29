import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import QThread, pyqtSignal
import docker
import logging

# Configure logging

logging.basicConfig(filename='monitor_log.log', level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')



class ResourceGraphWidget(QWidget):
    def __init__(self, container_name):
        super().__init__()
        self.container_name = container_name
        self.initUI()

    def initUI(self):
        self.setWindowTitle(f"Resource Usage for {self.container_name}")
        self.setGeometry(100, 100, 800, 600)
        layout = QVBoxLayout()

        self.cpu_plot = pg.PlotWidget()
        self.memory_plot = pg.PlotWidget()
        self.disk_plot = pg.PlotWidget()

        layout.addWidget(self.cpu_plot)
        layout.addWidget(self.memory_plot)
        layout.addWidget(self.disk_plot)

        self.setLayout(layout)

        self.cpu_curve = self.cpu_plot.plot(pen='r', name='CPU Usage (%)')
        self.memory_curve = self.memory_plot.plot(pen='g', name='Memory Usage (MB)')
        self.disk_curve = self.disk_plot.plot(pen='b', name='Disk Usage (MB)')

        self.cpu_data = []
        self.memory_data = []
        self.disk_data = []
        self.timestamps = []

    def update_graph(self, cpu_usage, memory_usage, disk_usage):
        try:
            self.cpu_data.append(cpu_usage)
            self.memory_data.append(memory_usage)
            self.disk_data.append(disk_usage)
            self.timestamps.append(len(self.timestamps) + 1)

            self.cpu_curve.setData(self.timestamps, self.cpu_data)
            self.memory_curve.setData(self.timestamps, self.memory_data)
            self.disk_curve.setData(self.timestamps, self.disk_data)

            self.cpu_plot.setLabel('left', 'CPU Usage (%)')
            self.cpu_plot.setLabel('bottom', 'Time')
            self.cpu_plot.addLegend()

            self.memory_plot.setLabel('left', 'Memory Usage (MB)')
            self.memory_plot.setLabel('bottom', 'Time')
            self.memory_plot.addLegend()

            self.disk_plot.setLabel('left', 'Disk Usage (MB)')
            self.disk_plot.setLabel('bottom', 'Time')
            self.disk_plot.addLegend()

           # logger.info(f"Updated graphs: CPU Usage={cpu_usage}%, Memory Usage={memory_usage}MB, Disk Usage={disk_usage}MB")
        except Exception as e:
            logger.error(f"Error updating graphs: {e}")

class ResourceMonitorThread(QThread):
    update_graph = pyqtSignal(float, float, float)

    def __init__(self, container):
        super().__init__()
        self.container = container
        self.client = docker.from_env()

    def run(self):
        prev_cpu = None
        prev_system = None

        while True:
            try:
                # Check if the container is running
                container_state = self.container.attrs['State']['Status']
                if container_state != 'running':
                    logger.info(f"Container {self.container.name} is not running. Skipping stats collection.")
                    self.update_graph.emit(0.0, 0.0, 0.0)
                    self.sleep(1)
                    break
                
                stats = self.container.stats(stream=False)
                cpu_stats = stats.get('cpu_stats', {})
                precpu_stats = stats.get('precpu_stats', cpu_stats)

                cpu_total = cpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                cpu_system = cpu_stats.get('system_cpu_usage', 0)
                precpu_total = precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                precpu_system = precpu_stats.get('system_cpu_usage', 0)

                num_cpus = len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', [1]))

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

                memory_usage_bytes = stats.get('memory_stats', {}).get('usage', 0)
                memory_usage_mb = memory_usage_bytes / (1024 * 1024)
                
                disk_usage_mb = self.get_disk_usage()

                self.update_graph.emit(cpu_usage, memory_usage_mb, disk_usage_mb)
            except KeyError as e:
                logger.warning(f"KeyError while fetching stats: {e}")
                self.update_graph.emit(0.0, 0.0, 0.0)
            except docker.errors.APIError as e:
                logger.error(f"APIError while fetching stats: {e}")
                self.update_graph.emit(0.0, 0.0, 0.0)
            except Exception as e:
                logger.error(f"Unexpected error while fetching stats: {e}")
                self.update_graph.emit(0.0, 0.0, 0.0)

            self.sleep(1)

    def get_disk_usage(self):
        try:
            exec_id = self.client.api.exec_create(self.container.id, ['df', '-h'])
            output = self.client.api.exec_start(exec_id, stream=False)
            output = output.decode('utf-8')
            
            lines = output.splitlines()
            if len(lines) > 1:
                usage_info = lines[1].split()
                if len(usage_info) >= 5:
                    used_space = usage_info[2]
                    #logger.info(f"Disk usage: {used_space}")
                    return float(used_space.replace('G', '').replace('M', ''))  # Simplified, needs proper parsing
            return 0.0
        except Exception as e:
            if "409" in str(e):
                logger.info(f"Container {self.container.id} is not running!")
                return 0.0
            else:
                logger.error(f"Error occurred while getting disk usage: {e}")
                return 0.0