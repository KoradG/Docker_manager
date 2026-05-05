import signal
import sys

from PyQt5.QtWidgets import QApplication
from docker_gui import DockerGui

# Ctrl+C-t a PTY-ban futó bash kapja meg, nem a Python folyamat.
# Ez a sor védi az alkalmazást attól, hogy véletlenül SIGINT-re haljon meg.
signal.signal(signal.SIGINT, signal.SIG_IGN)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = DockerGui()
    gui.show()
    sys.exit(app.exec_())