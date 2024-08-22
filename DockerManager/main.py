import sys
from PyQt5.QtWidgets import QApplication
from docker_gui import DockerGui


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = DockerGui()
    gui.show()
    sys.exit(app.exec_())
