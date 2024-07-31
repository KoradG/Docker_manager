# resource_monitor.py
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import QThread, pyqtSignal
import docker

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
                memory_limit_bytes = stats.get('memory_stats', {}).get('limit', 1)
                memory_usage_mb = memory_usage_bytes / (1024 * 1024)
                
                disk_usage_mb = self.get_disk_usage()

                self.update_graph.emit(cpu_usage, memory_usage_mb, disk_usage_mb)
            except KeyError as e:
                self.update_graph.emit(0.0, 0.0, 0.0)
            except docker.errors.APIError as e:
                pass
            except Exception as e:
                pass

            self.sleep(1)

    def get_disk_usage(self):
        # Replace this with actual disk usage calculation if needed
        return np.random.random() * 100
