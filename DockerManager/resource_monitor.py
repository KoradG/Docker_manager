import logging
import collections
import time
import docker

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QThread, pyqtSignal, Qt

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.FileHandler('monitor_log.log')
    _handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(_handler)

# How many data points to keep visible
HISTORY = 60


class ResourceGraphWidget(QWidget):
    def __init__(self, container_name):
        super().__init__()
        self.container_name = container_name

        self.cpu_data  = collections.deque([0.0] * HISTORY, maxlen=HISTORY)
        self.ram_data  = collections.deque([0.0] * HISTORY, maxlen=HISTORY)
        self.disk_data = collections.deque([0.0] * HISTORY, maxlen=HISTORY)
        self.xs = list(range(HISTORY))

        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"Resource Monitor – {self.container_name}")
        self.setMinimumSize(800, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel(f"📊  {self.container_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "color: #4fc3f7; font-size: 14px; font-weight: bold; padding: 4px;"
        )
        layout.addWidget(title)

        # Dark matplotlib figure with three subplots
        self.figure = Figure(figsize=(8, 6), facecolor='#1e1e1e')
        self.figure.subplots_adjust(hspace=0.45, left=0.08, right=0.97,
                                    top=0.93, bottom=0.07)

        self.ax_cpu  = self.figure.add_subplot(3, 1, 1)
        self.ax_ram  = self.figure.add_subplot(3, 1, 2)
        self.ax_disk = self.figure.add_subplot(3, 1, 3)

        for ax, title_text, color, ylabel in [
            (self.ax_cpu,  'CPU Usage',    '#4fc3f7', '%'),
            (self.ax_ram,  'RAM Usage',    '#4ec9b0', 'MB'),
            (self.ax_disk, 'Disk Usage',   '#dcdcaa', 'MB'),
        ]:
            ax.set_facecolor('#141414')
            ax.set_title(title_text, color=color, fontsize=9, pad=3)
            ax.set_ylabel(ylabel, color='#9d9d9d', fontsize=8)
            ax.tick_params(colors='#6a6a6a', labelsize=7)
            ax.spines['bottom'].set_color('#3a3a3a')
            ax.spines['top'].set_color('#3a3a3a')
            ax.spines['left'].set_color('#3a3a3a')
            ax.spines['right'].set_color('#3a3a3a')
            ax.set_xlim(0, HISTORY - 1)
            ax.grid(True, color='#2a2a2a', linewidth=0.5)

        self.line_cpu,  = self.ax_cpu.plot(
            self.xs, list(self.cpu_data),  color='#4fc3f7', linewidth=1.2)
        self.line_ram,  = self.ax_ram.plot(
            self.xs, list(self.ram_data),  color='#4ec9b0', linewidth=1.2)
        self.line_disk, = self.ax_disk.plot(
            self.xs, list(self.disk_data), color='#dcdcaa', linewidth=1.2)

        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background: #1e1e1e;")
        layout.addWidget(self.canvas)

    def update_graph(self, cpu: float, ram: float, disk: float):
        """Slot – receives (cpu%, ram_mb, disk_mb) from ResourceMonitorThread."""
        self.cpu_data.append(cpu)
        self.ram_data.append(ram)
        self.disk_data.append(disk)

        data_y = list(self.cpu_data)
        self.line_cpu.set_ydata(data_y)
        self.ax_cpu.set_ylim(0, max(max(data_y) * 1.2, 5))

        data_y = list(self.ram_data)
        self.line_ram.set_ydata(data_y)
        self.ax_ram.set_ylim(0, max(max(data_y) * 1.2, 10))

        data_y = list(self.disk_data)
        self.line_disk.set_ydata(data_y)
        self.ax_disk.set_ylim(0, max(max(data_y) * 1.2, 10))

        self.canvas.draw_idle()


class ResourceMonitorThread(QThread):
    update_graph = pyqtSignal(float, float, float)

    def __init__(self, container):
        super().__init__()
        self.container = container
        self._running = True

    def run(self):
        prev_cpu = None
        prev_system = None

        while self._running:
            try:
                self.container.reload()
                if self.container.status != 'running':
                    self.update_graph.emit(0.0, 0.0, 0.0)
                    time.sleep(1)
                    break

                stats = self.container.stats(stream=False)

                if not stats:
                    time.sleep(1)
                    continue

                cpu_stats    = stats.get('cpu_stats', {})
                precpu_stats = stats.get('precpu_stats', cpu_stats)

                cpu_total  = cpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                cpu_system = cpu_stats.get('system_cpu_usage', 0)

                percpu = cpu_stats.get('cpu_usage', {}).get('percpu_usage')
                num_cpus = len(percpu) if percpu else 1

                if prev_cpu is not None and prev_system is not None:
                    cpu_delta    = cpu_total  - prev_cpu
                    system_delta = cpu_system - prev_system
                    if system_delta > 0 and cpu_delta > 0:
                        cpu_usage = (cpu_delta / system_delta) * num_cpus * 100.0
                    else:
                        cpu_usage = 0.0
                else:
                    cpu_usage = 0.0

                prev_cpu    = cpu_total
                prev_system = cpu_system

                mem_stats = stats.get('memory_stats', {})
                cache     = mem_stats.get('stats', {}).get('cache', 0)
                ram_bytes = mem_stats.get('usage', 0) - cache
                ram_mb    = ram_bytes / (1024 * 1024)

                disk_mb = self._get_disk_usage(stats)

                self.update_graph.emit(cpu_usage, ram_mb, disk_mb)

            except docker.errors.APIError as e:
                logger.error(f"APIError fetching stats: {e}")
                self.update_graph.emit(0.0, 0.0, 0.0)
            except Exception as e:
                logger.error(f"Unexpected error fetching stats: {e}")
                self.update_graph.emit(0.0, 0.0, 0.0)

            time.sleep(1)

    def stop(self):
        self._running = False

    def _get_disk_usage(self, stats: dict) -> float:
        try:
            storage = stats.get('storage_stats', {})
            used = storage.get('read_write_layer', None)
            if used is None:
                blkio = stats.get('blkio_stats', {})
                io_service = blkio.get('io_service_bytes_recursive') or []
                write_bytes = sum(
                    e.get('value', 0) for e in io_service if e.get('op', '').lower() == 'write'
                )
                return write_bytes / (1024 * 1024)
            return used / (1024 * 1024)
        except Exception as e:
            logger.error(f"Disk usage error: {e}")
            return 0.0