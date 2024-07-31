import sys
from PyQt5.QtWidgets import QApplication
from docker_gui import DockerGUI

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = DockerGUI()
    gui.show()
    sys.exit(app.exec_())
