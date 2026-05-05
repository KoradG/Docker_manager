import os
import re
import subprocess
import socket
import docker
import pty
import fcntl
import termios
import struct
import pyte

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QLabel, QDialog,
    QFileDialog, QMessageBox, QFrame, QDialogButtonBox,
    QProgressDialog, QMenu, QScrollArea, QSplitter, QStackedWidget,
    QFormLayout, QSpinBox, QComboBox, QProgressBar
)
from PyQt5.QtGui import QFont, QColor, QTextCursor, QPainter, QFontMetrics
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

from logs import Logger
from resource_monitor import ResourceGraphWidget, ResourceMonitorThread
from swarm import SwarmManager
from podman_utils import (
    get_podman_client, is_podman_available,
    PodmanCapabilities,
)


# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

DARK_THEME = """
QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: 'Segoe UI', Ubuntu, sans-serif;
    font-size: 13px;
}
QTextEdit, QLineEdit {
    background-color: #141414;
    color: #d4d4d4;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px;
}
QTextEdit:focus, QLineEdit:focus {
    border-color: #007acc;
}
QScrollBar:vertical {
    background: #1e1e1e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #4a4a4a;
    border-radius: 4px;
}
QScrollBar:horizontal {
    background: #1e1e1e;
    height: 8px;
}
QScrollBar::handle:horizontal {
    background: #4a4a4a;
    border-radius: 4px;
}
QProgressBar {
    background-color: #2d2d2d;
    border: none;
    border-radius: 3px;
}
QProgressBar::chunk {
    background-color: #007acc;
    border-radius: 3px;
}
QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 120px;
}
QComboBox:hover { border-color: #007acc; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    selection-background-color: #264f78;
}
QTableWidget {
    background-color: #1e1e1e;
    gridline-color: #2d2d2d;
    border: none;
}
QTableWidget::item { padding: 4px; }
QTableWidget::item:selected { background-color: #264f78; }
QHeaderView::section {
    background-color: #252526;
    color: #9cdcfe;
    padding: 6px;
    border: 1px solid #3a3a3a;
    font-weight: bold;
}
QSplitter::handle { background-color: #3a3a3a; width: 1px; height: 1px; }
QScrollArea { border: none; background: transparent; }
QDialog { background-color: #1e1e1e; }
QMessageBox { background-color: #1e1e1e; }
QInputDialog { background-color: #1e1e1e; }
QLabel { color: #d4d4d4; }
"""

NAV_BTN_STYLE = """
QPushButton {
    background-color: transparent;
    color: #9d9d9d;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover { color: #d4d4d4; }
QPushButton:checked {
    color: #4fc3f7;
    border-bottom: 2px solid #4fc3f7;
}
"""

ACTION_BTN_STYLE = """
QPushButton {
    background-color: #2a2a2a;
    color: #d4d4d4;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px 10px;
    text-align: left;
}
QPushButton:hover { background-color: #3a3a3a; border-color: #007acc; }
QPushButton:pressed { background-color: #264f78; }
"""

MONITOR_BTN_STYLE = """
QPushButton {
    background-color: #1e3a5f;
    color: #4fc3f7;
    border: 1px solid #007acc;
    border-radius: 4px;
    padding: 6px 10px;
}
QPushButton:hover { background-color: #264f78; }
"""

TABLE_BTN_STYLE = """
QPushButton {
    background-color: #2a2a2a;
    color: #9cdcfe;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px 10px;
    min-width: 70px;
}
QPushButton:hover { background-color: #264f78; border-color: #007acc; }
QPushButton:pressed { background-color: #1e3a5f; }
"""

DANGER_BTN_STYLE = """
QPushButton {
    background-color: #3a1a1a;
    color: #f44747;
    border: 1px solid #5a2a2a;
    border-radius: 4px;
    padding: 4px 10px;
    min-width: 70px;
}
QPushButton:hover { background-color: #5a2a2a; }
"""

# ---------------------------------------------------------------------------
# ANSI strip
# ---------------------------------------------------------------------------

ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


# ---------------------------------------------------------------------------
# Terminal: ANSI color table, 256-color helper, key map
# ---------------------------------------------------------------------------

_ANSI_COLORS = {
    'black':         QColor('#1e1e1e'),
    'red':           QColor('#f44747'),
    'green':         QColor('#4ec9b0'),
    'brown':         QColor('#dcdcaa'),   # pyte uses 'brown' for dark yellow
    'blue':          QColor('#4fc3f7'),
    'magenta':       QColor('#c678dd'),
    'cyan':          QColor('#56b6c2'),
    'white':         QColor('#d4d4d4'),
    'brightblack':   QColor('#4a4a4a'),
    'brightred':     QColor('#f47a7a'),
    'brightgreen':   QColor('#6ef7d8'),
    'brightyellow':  QColor('#ffffa0'),
    'brightblue':    QColor('#90d0ff'),
    'brightmagenta': QColor('#e090f0'),
    'brightcyan':    QColor('#80e0e8'),
    'brightwhite':   QColor('#ffffff'),
}

def _256_color(n: int) -> QColor:
    """Convert a 256-palette index to QColor."""
    if n < 16:
        return list(_ANSI_COLORS.values())[n]
    if n < 232:           # 6×6×6 RGB cube
        n -= 16
        b = n % 6;  g = (n // 6) % 6;  r = n // 36
        v = lambda x: 0 if x == 0 else 55 + x * 40
        return QColor(v(r), v(g), v(b))
    val = 8 + (n - 232) * 10   # grayscale ramp
    return QColor(val, val, val)

_KEY_MAP: dict = {
    Qt.Key_Return:    b'\r',
    Qt.Key_Enter:     b'\r',
    Qt.Key_Backspace: b'\x7f',
    Qt.Key_Tab:       b'\t',
    Qt.Key_Escape:    b'\x1b',
    Qt.Key_Up:        b'\x1b[A',
    Qt.Key_Down:      b'\x1b[B',
    Qt.Key_Right:     b'\x1b[C',
    Qt.Key_Left:      b'\x1b[D',
    Qt.Key_Home:      b'\x1b[H',
    Qt.Key_End:       b'\x1b[F',
    Qt.Key_PageUp:    b'\x1b[5~',
    Qt.Key_PageDown:  b'\x1b[6~',
    Qt.Key_Delete:    b'\x1b[3~',
    Qt.Key_Insert:    b'\x1b[2~',
    Qt.Key_F1:        b'\x1bOP',
    Qt.Key_F2:        b'\x1bOQ',
    Qt.Key_F3:        b'\x1bOR',
    Qt.Key_F4:        b'\x1bOS',
    Qt.Key_F5:        b'\x1b[15~',
    Qt.Key_F6:        b'\x1b[17~',
    Qt.Key_F7:        b'\x1b[18~',
    Qt.Key_F8:        b'\x1b[19~',
    Qt.Key_F9:        b'\x1b[20~',
    Qt.Key_F10:       b'\x1b[21~',
    Qt.Key_F11:       b'\x1b[23~',
    Qt.Key_F12:       b'\x1b[24~',
}


# ---------------------------------------------------------------------------
# PTY + pyte terminal emulator widget
# ---------------------------------------------------------------------------

class ShellWidget(QWidget):
    """
    Full VT100/XTERM terminal emulator.

    Features:
    - pyte.HistoryScreen: 2000-line scrollback buffer
    - QPainter cell-by-cell rendering (256 colours, bold, underline, reverse)
    - PTY master/slave pair + automatic TIOCSWINSZ size sync
    - Scrolling: mouse wheel + Shift+PageUp/Down
    - Ctrl+C/D/Z and all control codes go to the PTY, not the application
    - Screen state is preserved across container switches
    """

    _DEFAULT_FG = QColor('#c8c8c8')
    _DEFAULT_BG = QColor('#0d0d0d')
    _CURSOR_COL = QColor('#4fc3f7')
    _SCROLL_IND = QColor('#264f78')     # scroll position indicator bar

    _HISTORY    = 2000                  # number of lines kept in history

    def __init__(self, parent=None):
        super().__init__(parent)
        self.binary     = "docker"
        self.process    = None
        self.master_fd  = None
        self.notifier   = None
        self._connected = False
        self._scroll_offset = 0         # 0 = bottom (live view), N = scrolled N lines up

        # Monospace font + cell metrics
        self._font = QFont("Monospace", 11)
        self._font.setStyleHint(QFont.Monospace)
        fm = QFontMetrics(self._font)
        self._cw = max(fm.horizontalAdvance('M'), 1)
        self._ch = max(fm.height(), 1)

        self._cols = 80
        self._rows = 24
        self._init_screen()

        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.IBeamCursor)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumSize(self._cw * 40, self._ch * 10)
        self.setStyleSheet("background-color: #0d0d0d;")

    # ── pyte ──────────────────────────────────────────────────────────────

    def _init_screen(self):
        self._screen = pyte.HistoryScreen(self._cols, self._rows,
                                          history=self._HISTORY)
        self._stream = pyte.Stream(self._screen)

    # ── Resize ────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = max(self.width()  // self._cw, 10)
        new_rows = max(self.height() // self._ch,  5)
        if new_cols != self._cols or new_rows != self._rows:
            self._cols = new_cols
            self._rows = new_rows
            self._screen.resize(self._rows, self._cols)
            self._push_pty_size()

    def _push_pty_size(self):
        if self.master_fd is None:
            return
        try:
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ,
                        struct.pack('HHHH', self._rows, self._cols, 0, 0))
        except OSError:
            pass

    # ── Scrollback helpers ────────────────────────────────────────────────

    def _max_scroll(self) -> int:
        return len(self._screen.history.top)

    def _scroll_by(self, lines: int):
        """Positive = scroll up (into history), negative = scroll down."""
        self._scroll_offset = max(0, min(
            self._scroll_offset + lines, self._max_scroll()
        ))
        self.update()

    def _get_display_lines(self) -> list:
        """
        Return self._rows line dicts to render.
        Each dict maps col index → pyte.Char.
        At offset 0 returns the live screen buffer.
        """
        if self._scroll_offset == 0:
            return [self._screen.buffer[r] for r in range(self._rows)]

        history = list(self._screen.history.top)
        n_hist  = len(history)
        total   = n_hist + self._rows
        end     = total - self._scroll_offset
        start   = max(0, end - self._rows)

        lines = []
        for i in range(start, end):
            lines.append(history[i] if i < n_hist
                         else self._screen.buffer[i - n_hist])
        # Pad with empty dicts if we hit the very beginning of history
        while len(lines) < self._rows:
            lines.insert(0, {})
        return lines

    # ── Painting ──────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setFont(self._font)
        painter.fillRect(self.rect(), self._DEFAULT_BG)

        if not self._connected:
            painter.setPen(QColor('#6a6a6a'))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "Select a running container…")
            painter.end()
            return

        lines    = self._get_display_lines()
        scrolled = self._scroll_offset > 0
        # Hide cursor when scrolled back
        cursor_x = self._screen.cursor.x if not scrolled else -1
        cursor_y = self._screen.cursor.y if not scrolled else -1

        for row, line in enumerate(lines):
            for col in range(self._cols):
                char = line.get(col)
                if char is None:
                    continue

                fg = self._color(char.fg, fg=True)
                bg = self._color(char.bg, fg=False)

                if char.reverse:
                    fg, bg = bg, fg

                is_cursor = (col == cursor_x and row == cursor_y)
                x = col * self._cw
                y = row * self._ch

                cell_bg = self._CURSOR_COL if is_cursor else bg
                if cell_bg != self._DEFAULT_BG:
                    painter.fillRect(x, y, self._cw, self._ch, cell_bg)

                glyph = char.data
                if glyph and glyph != ' ':
                    if char.bold:
                        f = QFont(self._font)
                        f.setBold(True)
                        painter.setFont(f)
                    else:
                        painter.setFont(self._font)
                    text_fg = self._DEFAULT_BG if is_cursor else fg
                    painter.setPen(text_fg)
                    painter.drawText(x, y, self._cw, self._ch,
                                     Qt.AlignLeft | Qt.AlignVCenter, glyph)

                if char.underscore:
                    painter.setPen(fg)
                    painter.drawLine(x, y + self._ch - 2,
                                     x + self._cw - 1, y + self._ch - 2)

        # Scroll position indicator (right edge, 3px wide)
        if scrolled and self._max_scroll() > 0:
            ratio     = self._scroll_offset / self._max_scroll()
            bar_h     = self.height()
            thumb_h   = max(20, int(bar_h * self._rows /
                                    (self._max_scroll() + self._rows)))
            thumb_y   = int((bar_h - thumb_h) * (1.0 - ratio))
            painter.fillRect(self.width() - 3, 0, 3, bar_h,
                             QColor('#2a2a2a'))
            painter.fillRect(self.width() - 3, thumb_y, 3, thumb_h,
                             self._SCROLL_IND)

        painter.end()

    def _color(self, val: str, fg: bool) -> QColor:
        if val == 'default' or not val:
            return self._DEFAULT_FG if fg else self._DEFAULT_BG
        if val in _ANSI_COLORS:
            return _ANSI_COLORS[val]
        if len(val) == 6:
            try:
                return QColor('#' + val)
            except Exception:
                pass
        return self._DEFAULT_FG if fg else self._DEFAULT_BG

    # ── Keyboard ──────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()
        text = event.text()

        # ── Scrollback shortcuts (Shift+PgUp / Shift+PgDn) ──
        if mods & Qt.ShiftModifier:
            if key == Qt.Key_PageUp:
                self._scroll_by(self._rows)
                event.accept()
                return
            if key == Qt.Key_PageDown:
                self._scroll_by(-self._rows)
                event.accept()
                return

        # ── Nothing to do if not connected ──────────────────
        if self.master_fd is None:
            super().keyPressEvent(event)
            return

        # Any keypress while scrolled → jump to bottom first
        if self._scroll_offset > 0:
            self._scroll_offset = 0

        seq = _KEY_MAP.get(key)

        # Ctrl+A…Z → \x01–\x1A
        # Use the key code directly — event.text() returns an empty string
        # for Ctrl+letter on some Qt/Linux configurations.
        if seq is None and (mods & Qt.ControlModifier):
            if Qt.Key_A <= key <= Qt.Key_Z:
                seq = bytes([key - Qt.Key_A + 1])

        if seq is None and text:
            seq = text.encode('utf-8')

        if seq:
            try:
                os.write(self.master_fd, seq)
            except OSError:
                self.disconnect_shell()
            event.accept()      # prevent Qt from processing the event further
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        """Mouse wheel → scroll the history buffer."""
        delta = event.angleDelta().y()   # positive = scroll up
        lines = (delta // 40) * 3        # ~3 lines per wheel notch
        self._scroll_by(lines)
        event.accept()

    def mousePressEvent(self, _event):
        self.setFocus()

    # ── Connection ────────────────────────────────────────────────────────

    def connect_container(self, container_id, container_name):
        self.disconnect_shell()
        self._cols = max(self.width()  // self._cw, 10)
        self._rows = max(self.height() // self._ch,  5)
        self._init_screen()
        self._scroll_offset = 0
        try:
            self.master_fd, slave_fd = pty.openpty()

            # ── Disable ISIG on the slave PTY ────────────────────────────
            # By default the slave PTY has ISIG=on, meaning \x03 (Ctrl+C)
            # generates SIGINT for the slave's process (docker exec), which
            # then exits and drops the connection. With ISIG=off, \x03 is
            # treated as a plain data byte that passes through docker exec
            # to the container's internal PTY, where bash receives SIGINT
            # and interrupts the current command — the correct behaviour.
            attrs = termios.tcgetattr(slave_fd)
            attrs[3] &= ~(termios.ISIG | termios.IXON)   # c_lflag, c_iflag
            termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)

            self._push_pty_size()
            self.process = subprocess.Popen(
                [self.binary, 'exec', '-it', container_id,
                 '/bin/sh', '-c', 'bash 2>/dev/null || sh'],
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                close_fds=True,
            )
            os.close(slave_fd)
            self._connected = True
            self._start_notifier()
            self.setFocus()
            self.update()
        except Exception as e:
            self._connected = False
            self.update()

    def _detach(self):
        """Pause reading – keep the PTY and process alive."""
        self._stop_notifier()

    def _reattach(self, process, master_fd, screen, container_name):
        """Restore a previously saved session."""
        self._stop_notifier()
        self.process    = process
        self.master_fd  = master_fd
        if screen is not None:
            self._screen = screen
            self._stream = pyte.Stream(self._screen)
        self._connected     = True
        self._scroll_offset = 0
        self._push_pty_size()
        self._start_notifier()
        self.setFocus()
        self.update()

    def disconnect_shell(self):
        self._stop_notifier()
        self._connected = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                pass
            self.process = None
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        self.update()

    # ── Notifier ──────────────────────────────────────────────────────────

    def _start_notifier(self):
        from PyQt5.QtCore import QSocketNotifier
        if self.master_fd is not None:
            self.notifier = QSocketNotifier(
                self.master_fd, QSocketNotifier.Read, self)
            self.notifier.activated.connect(self._read_output)

    def _stop_notifier(self):
        if self.notifier:
            self.notifier.setEnabled(False)
            self.notifier.activated.disconnect()
            self.notifier = None

    def _read_output(self):
        if self.master_fd is None:
            return
        try:
            data = os.read(self.master_fd, 4096)
            if data:
                prev_hist = len(self._screen.history.top)
                self._stream.feed(data.decode('utf-8', errors='replace'))
                # If the user has scrolled up, keep the scroll position stable
                if self._scroll_offset > 0:
                    pushed = len(self._screen.history.top) - prev_hist
                    self._scroll_offset = min(
                        self._scroll_offset + pushed,
                        self._max_scroll()
                    )
                self.update()
        except OSError:
            self._stop_notifier()
            self._connected = False
            self.update()


# ---------------------------------------------------------------------------
# Pull image thread
# ---------------------------------------------------------------------------

class PullImageThread(QThread):
    progress = pyqtSignal(str)

    def __init__(self, client, repository):
        super().__init__()
        self.client = client
        self.repository = repository

    def run(self):
        try:
            self.progress.emit("Starting pull…")
            for chunk in self.client.api.pull(self.repository, stream=True, decode=True):
                if 'status' in chunk:
                    msg = chunk['status']
                    if 'progressDetail' in chunk and chunk['progressDetail']:
                        detail = chunk['progressDetail']
                        if 'current' in detail and 'total' in detail:
                            pct = int(detail['current'] / detail['total'] * 100)
                            msg += f" {pct}%"
                    self.progress.emit(msg)
            self.progress.emit("Pull complete!")
        except docker.errors.APIError as e:
            self.progress.emit(f"API error: {e}")
        except Exception as e:
            self.progress.emit(f"Error: {e}")


# ---------------------------------------------------------------------------
# Container button
# ---------------------------------------------------------------------------

class ContainerButton(QPushButton):
    _STATUS = {
        'running': ('#1a3a2a', '#4ec9b0'),
        'paused':  ('#3a3000', '#dcdcaa'),
        'exited':  ('#3a0d0d', '#f44747'),
        'created': ('#1e2a3a', '#9cdcfe'),
    }

    def __init__(self, container):
        super().__init__()
        self.container = container
        self.setCheckable(True)
        self._apply_style()

    def _apply_style(self):
        status = self.container.status
        bg, fg = self._STATUS.get(status, ('#2a2a2a', '#9d9d9d'))
        self.setText(f"  {self.container.name}")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {fg}55;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                min-width: 110px;
                text-align: left;
            }}
            QPushButton:hover {{ border-color: {fg}; }}
            QPushButton:checked {{ border: 2px solid {fg}; }}
        """)


# ---------------------------------------------------------------------------
# Containers view
# ---------------------------------------------------------------------------

class ContainersView(QWidget):
    log_message = pyqtSignal(str)

    def __init__(self, docker_client, logger):
        super().__init__()
        self.docker_client = docker_client
        self.logger = logger
        self.selected_container = None
        self.container_buttons = []
        self.monitor_windows = {}
        self.resource_thread = None
        self.shell_sessions = {}   # container_id -> {'process': ..., 'thread': ..., 'text': ...}
        self._switching = False    # guard against refresh during container switch
        self.podman_caps = None    # PodmanCapabilities | None – set by DockerGui
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # ── Container buttons row ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setFixedHeight(50)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "background: #252526; border-radius: 4px; border: 1px solid #3a3a3a;"
        )
        self.btn_container = QWidget()
        self.btn_container.setStyleSheet("background: transparent;")
        self.btn_layout = QHBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(6, 4, 6, 4)
        self.btn_layout.setSpacing(6)
        self.btn_layout.addStretch()
        scroll.setWidget(self.btn_container)
        layout.addWidget(scroll)

        # ── Main splitter: left actions | shell ───────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left panel
        left = QWidget()
        left.setFixedWidth(190)
        left.setStyleSheet("background: #252526; border-radius: 4px;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 8, 8)
        ll.setSpacing(4)

        def section_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "color: #6a6a6a; font-size: 10px; font-weight: bold; padding: 6px 0 2px 0;"
            )
            return lbl

        ll.addWidget(section_label("ACTIONS"))

        for icon, label, func in [
            ("▶", "Start",    self.start_container),
            ("■", "Stop",     self.stop_container),
            ("⏸", "Pause",    self.pause_container),
            ("▷", "Unpause",  self.unpause_container),
            ("📋", "Logs",    self.open_logs),
            ("🔍", "Inspect", self.inspect_container),
            ("🗑", "Remove",  self.remove_container),
        ]:
            btn = QPushButton(f"{icon}  {label}")
            btn.setStyleSheet(ACTION_BTN_STYLE)
            btn.clicked.connect(func)
            ll.addWidget(btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3a3a3a; margin: 4px 0;")
        ll.addWidget(sep)

        ll.addWidget(section_label("RESOURCES"))

        def resource_row(label_text, color):
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setFixedWidth(32)
            lbl.setStyleSheet("color: #6a6a6a; font-size: 11px;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(5)
            bar.setStyleSheet(
                f"QProgressBar {{ background: #2d2d2d; border: none; border-radius: 2px; }}"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}"
            )
            val = QLabel("—")
            val.setStyleSheet(f"color: {color}; font-size: 11px; min-width: 42px;")
            row.addWidget(lbl)
            row.addWidget(bar, 1)
            row.addWidget(val)
            return row, bar, val

        cpu_row, self.cpu_bar, self.cpu_val = resource_row("CPU", "#4fc3f7")
        ram_row, self.ram_bar, self.ram_val = resource_row("RAM", "#4ec9b0")
        disk_row, self.disk_bar, self.disk_val = resource_row("DSK", "#dcdcaa")
        ll.addLayout(cpu_row)
        ll.addLayout(ram_row)
        ll.addLayout(disk_row)

        self.graph_btn = QPushButton("📊  Open Monitor")
        self.graph_btn.setStyleSheet(MONITOR_BTN_STYLE)
        self.graph_btn.setEnabled(True)
        self.graph_btn.clicked.connect(self.open_monitor)
        ll.addWidget(self.graph_btn)

        ll.addStretch()
        splitter.addWidget(left)

        # Shell
        self.shell = ShellWidget()
        splitter.addWidget(self.shell)
        splitter.setSizes([190, 700])

        layout.addWidget(splitter, 1)

    # ── Container refresh ──────────────────────────────────────────────────

    def refresh(self):
        if self._switching:
            return
        selected_id = self.selected_container.id if self.selected_container else None

        for btn in self.container_buttons:
            btn.setParent(None)
        self.container_buttons.clear()
        # Remove last stretch
        item = self.btn_layout.takeAt(self.btn_layout.count() - 1)
        if item:
            del item

        try:
            containers = self.docker_client.containers.list(all=True)
        except Exception as e:
            self.log_message.emit(f"Error listing containers: {e}")
            containers = []

        for c in containers:
            btn = ContainerButton(c)
            if selected_id and c.id == selected_id:
                btn.setChecked(True)
            btn.clicked.connect(lambda _, container=c: self.select_container(container))
            self.btn_layout.addWidget(btn)
            self.container_buttons.append(btn)

        self.btn_layout.addStretch()

    def select_container(self, container):
        if self._switching:
            return
        # Skip if same container already selected
        if self.selected_container and self.selected_container.id == container.id:
            return
        self._switching = True
        try:
            for btn in self.container_buttons:
                btn.setChecked(btn.container.id == container.id)

            # Save current shell state before switching
            if self.selected_container:
                prev_id = self.selected_container.id
                self.shell_sessions[prev_id] = {
                    'screen':    self.shell._screen,
                    'process':   self.shell.process,
                    'master_fd': self.shell.master_fd,
                }
                self.shell._detach()

            self.selected_container = container
            self.log_message.emit(f"Selected: {container.name}  [{container.status}]")
            self._stop_resource_monitor()

            if container.status == 'running':
                self._start_resource_monitor(container)
                session = self.shell_sessions.get(container.id)
                if session and session.get('process') and session['process'].poll() is None:
                    self.shell._reattach(
                        session['process'],
                        session.get('master_fd'),
                        session.get('screen'),
                        container.name,
                    )
                else:
                    self.shell_sessions.pop(container.id, None)
                    self.shell.connect_container(container.id, container.name)
            else:
                self.shell.disconnect_shell()
        finally:
            self._switching = False

    # ── Resource monitor ───────────────────────────────────────────────────

    def _start_resource_monitor(self, container):
        self.resource_thread = ResourceMonitorThread(container)
        self.resource_thread.update_graph.connect(self._update_resources)
        self.resource_thread.start()

    def _stop_resource_monitor(self):
        if self.resource_thread:
            try:
                self.resource_thread.update_graph.disconnect()
            except Exception:
                pass
            self.resource_thread.stop()
            # Wait up to 1.5 s for the thread to exit cleanly.
            # Without this, Python's GC may destroy the QThread object while
            # it is still running, which triggers Qt's fatal abort (SIGABRT).
            self.resource_thread.wait(1500)
            self.resource_thread = None
        for bar, val in [
            (self.cpu_bar, self.cpu_val),
            (self.ram_bar, self.ram_val),
            (self.disk_bar, self.disk_val),
        ]:
            bar.setValue(0)
            val.setText("—")

    def _update_resources(self, cpu, ram, disk):
        self.cpu_bar.setValue(int(min(cpu, 100)))
        self.cpu_val.setText(f"{cpu:.1f}%")
        self.ram_bar.setValue(int(min(ram / 20, 100)))
        self.ram_val.setText(f"{ram:.0f}M")
        self.disk_bar.setValue(int(min(disk, 100)))
        self.disk_val.setText(f"{disk:.1f}M")

    # ── Helpers ────────────────────────────────────────────────────────────

    def _get_selected(self):
        if not self.selected_container:
            self.log_message.emit("No container selected.")
            return None
        try:
            return self.docker_client.containers.get(self.selected_container.id)
        except Exception as e:
            self.log_message.emit(f"Error: {e}")
            return None

    # ── Actions ────────────────────────────────────────────────────────────

    def start_container(self):
        c = self._get_selected()
        if c:
            try:
                c.start()
                self.log_message.emit(f"Started: {c.name}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error starting: {e}")

    def stop_container(self):
        c = self._get_selected()
        if c:
            try:
                c.stop()
                self.log_message.emit(f"Stopped: {c.name}")
                self._stop_resource_monitor()
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error stopping: {e}")

    def pause_container(self):
        c = self._get_selected()
        if c:
            if c.status != 'running':
                self.log_message.emit(f"{c.name} is not running.")
                return
            # Pause does not work with Podman + cgroups v1
            if self.podman_caps is not None and not self.podman_caps.pause_supported:
                self.log_message.emit(
                    f"⚠  Pause unavailable: Podman requires cgroups v2. "
                    f"Check: /sys/fs/cgroup/cgroup.controllers"
                )
                return
            try:
                c.pause()
                self.log_message.emit(f"Paused: {c.name}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error pausing: {e}")

    def unpause_container(self):
        c = self._get_selected()
        if c:
            try:
                c.unpause()
                self.log_message.emit(f"Unpaused: {c.name}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error unpausing: {e}")

    def open_shell(self):
        c = self._get_selected()
        if c:
            if c.status != 'running':
                self.log_message.emit(f"{c.name} is not running – cannot open shell.")
                return
            self.shell.connect_container(c.id, c.name)

    def open_logs(self):
        c = self._get_selected()
        if c:
            try:
                logs = c.logs(tail=200).decode('utf-8', errors='replace')
                self.log_message.emit(f"── Logs: {c.name} ──\n{logs}")
            except Exception as e:
                self.log_message.emit(f"Error fetching logs: {e}")

    def inspect_container(self):
        c = self._get_selected()
        if c:
            import json
            info = json.dumps(c.attrs, indent=2)
            self.log_message.emit(f"── Inspect: {c.name} ──\n{info}")

    def remove_container(self):
        c = self._get_selected()
        if c:
            reply = QMessageBox.question(
                self, 'Remove Container',
                f"Remove container '{c.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    c.remove(force=True)
                    self.log_message.emit(f"Removed: {c.name}")
                    self.selected_container = None
                    self.shell.disconnect_shell()
                    self._stop_resource_monitor()
                    # Close floating monitor window if open for this container
                    if c.id in self.monitor_windows:
                        win, thread = self.monitor_windows.pop(c.id)
                        thread.stop()
                        win.close()
                    self.refresh()
                except Exception as e:
                    self.log_message.emit(f"Error removing: {e}")

    def open_monitor(self):
        c = self._get_selected()
        if not c or c.status != 'running':
            self.log_message.emit("Select a running container to open the resource monitor.")
            return
        if c.id not in self.monitor_windows:
            win = QWidget()
            win.setWindowTitle(f"Resource Monitor – {c.name}")
            win.setGeometry(200, 200, 900, 600)
            win.setStyleSheet(DARK_THEME)
            layout = QVBoxLayout(win)
            graph = ResourceGraphWidget(c.name)
            layout.addWidget(graph)
            thread = ResourceMonitorThread(c)
            thread.update_graph.connect(graph.update_graph)
            thread.start()
            win.show()

            def on_close(event, t=thread):
                try:
                    t.update_graph.disconnect()
                except Exception:
                    pass
                t.stop()
                t.wait(1500)
                event.accept()

            win.closeEvent = on_close
            self.monitor_windows[c.id] = (win, thread)
        else:
            self.monitor_windows[c.id][0].show()
            self.monitor_windows[c.id][0].raise_()


# ---------------------------------------------------------------------------
# Images view
# ---------------------------------------------------------------------------

class ImagesView(QWidget):
    log_message = pyqtSignal(str)

    def __init__(self, docker_client, logger):
        super().__init__()
        self.docker_client = docker_client
        self.logger = logger
        self.pull_thread = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        pull_btn = QPushButton("⬇  Pull Image")
        pull_btn.setStyleSheet(TABLE_BTN_STYLE)
        pull_btn.clicked.connect(self.pull_image)
        toolbar.addWidget(pull_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Tags", "Remove", "Tag", "Push", "Run"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setStyleSheet("alternate-background-color: #252526;")
        layout.addWidget(self.table, 1)

    def refresh(self):
        try:
            images = self.docker_client.images.list()
        except Exception as e:
            self.log_message.emit(f"Error listing images: {e}")
            return

        self.table.setRowCount(len(images))
        for row, img in enumerate(images):
            tags = ', '.join(img.tags) if img.tags else img.short_id
            self.table.setItem(row, 0, QTableWidgetItem(img.short_id))
            self.table.setItem(row, 1, QTableWidgetItem(tags))

            rm_btn = QPushButton("Remove")
            rm_btn.setStyleSheet(DANGER_BTN_STYLE)
            rm_btn.clicked.connect(lambda _, i=img: self._remove_image(i))
            self.table.setCellWidget(row, 2, rm_btn)

            tag_btn = QPushButton("Tag")
            tag_btn.setStyleSheet(TABLE_BTN_STYLE)
            tag_btn.clicked.connect(lambda _, i=img: self._tag_image(i))
            self.table.setCellWidget(row, 3, tag_btn)

            push_btn = QPushButton("Push")
            push_btn.setStyleSheet(TABLE_BTN_STYLE)
            push_btn.clicked.connect(lambda _, i=img: self._push_image(i))
            self.table.setCellWidget(row, 4, push_btn)

            run_btn = QPushButton("Run")
            run_btn.setStyleSheet(TABLE_BTN_STYLE)
            menu = QMenu()
            menu.setStyleSheet("background: #2d2d2d; color: #d4d4d4; border: 1px solid #3a3a3a;")
            menu.addAction("Run (default)", lambda i=img: self._run_image(i))
            menu.addAction("Run (keep alive)", lambda i=img: self._run_image_keepalive(i))
            menu.addAction("Run with params…", lambda i=img: self._run_image_params(i))
            run_btn.setMenu(menu)
            self.table.setCellWidget(row, 5, run_btn)

    def pull_image(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
        except OSError:
            self.log_message.emit("No internet connection.")
            return

        repo, ok = QInputDialog.getText(
            self, "Pull Image", "Image name (e.g. ubuntu:latest):"
        )
        if not ok or not repo:
            return

        progress = QProgressDialog("Pulling image…", "Cancel", 0, 0, self)
        progress.setWindowTitle("Pull Image")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        self.pull_thread = PullImageThread(self.docker_client, repo)
        self.pull_thread.progress.connect(
            lambda msg: (self.log_message.emit(msg), progress.setLabelText(msg))
        )
        self.pull_thread.finished.connect(progress.close)
        self.pull_thread.finished.connect(self.refresh)
        self.pull_thread.start()

    def _remove_image(self, img):
        reply = QMessageBox.question(
            self, 'Remove Image', f"Remove image {img.short_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.docker_client.images.remove(img.id, force=True)
                self.log_message.emit(f"Removed image: {img.short_id}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error removing image: {e}")

    def _tag_image(self, img):
        tag, ok = QInputDialog.getText(self, "Tag Image", "New tag:")
        if ok and tag:
            try:
                img.tag(tag)
                self.log_message.emit(f"Tagged {img.short_id} as {tag}")
            except Exception as e:
                self.log_message.emit(f"Error tagging: {e}")

    def _push_image(self, img):
        repo, ok = QInputDialog.getText(self, "Push Image", "Repository:")
        if ok and repo:
            try:
                self.docker_client.images.push(repo)
                self.log_message.emit(f"Pushed {img.short_id} to {repo}")
            except Exception as e:
                self.log_message.emit(f"Error pushing: {e}")

    def _run_image(self, img):
        try:
            exposed = img.attrs.get('Config', {}).get('ExposedPorts', {})
            ports = {p: ('0.0.0.0', int(p.split('/')[0])) for p in exposed}
            container = self.docker_client.containers.run(
                img.id, detach=True, network_mode="bridge", ports=ports
            )
            self.log_message.emit(f"Started container {container.short_id} from {img.short_id}")
        except Exception as e:
            self.log_message.emit(f"Error running image: {e}")

    def _run_image_keepalive(self, img):
        """Run container with sleep infinity so it stays alive indefinitely."""
        try:
            tags = img.tags
            name = tags[0].replace(':', '_').replace('/', '_') if tags else img.short_id
            name = f"{name}_keepalive"
            container = self.docker_client.containers.run(
                img.id,
                command="sleep infinity",
                name=name,
                detach=True,
                network_mode="bridge",
            )
            self.log_message.emit(
                f"Started keep-alive container '{container.name}' ({container.short_id})"
            )
        except Exception as e:
            self.log_message.emit(f"Error starting keep-alive container: {e}")

    def _run_image_params(self, img):
        dialog = QDialog(self)
        dialog.setWindowTitle("Run with Parameters")
        layout = QFormLayout(dialog)

        cpu_spin = QSpinBox()
        cpu_spin.setRange(1, 32)
        mem_spin = QSpinBox()
        mem_spin.setRange(64, 32768)
        mem_spin.setValue(512)
        cmd_edit = QLineEdit()
        cmd_edit.setPlaceholderText("sleep infinity  (leave empty for image default)")
        ports_edit = QLineEdit()
        ports_edit.setPlaceholderText("8080:80, 443:443")
        vols_edit = QLineEdit()
        vols_edit.setPlaceholderText("/host:/container")
        env_edit = QLineEdit()
        env_edit.setPlaceholderText("KEY=VALUE, KEY2=VALUE2")
        restart_combo = QComboBox()
        restart_combo.addItems(["no", "always", "unless-stopped", "on-failure"])

        layout.addRow("CPUs:", cpu_spin)
        layout.addRow("Memory (MB):", mem_spin)
        layout.addRow("Command:", cmd_edit)
        layout.addRow("Ports:", ports_edit)
        layout.addRow("Volumes:", vols_edit)
        layout.addRow("Env vars:", env_edit)
        layout.addRow("Restart:", restart_combo)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        if dialog.exec_() != QDialog.Accepted:
            return

        run_args = {
            'image': img.id, 'detach': True,
            'cpu_quota': cpu_spin.value() * 100000,
            'cpu_period': 100000,
            'mem_limit': f"{mem_spin.value()}m",
            'restart_policy': {'Name': restart_combo.currentText()},
        }
        if cmd_edit.text().strip():
            run_args['command'] = cmd_edit.text().strip()
        if ports_edit.text():
            ports = {}
            for p in ports_edit.text().split(','):
                parts = p.strip().split(':')
                if len(parts) == 2:
                    ports[int(parts[1])] = int(parts[0])
            run_args['ports'] = ports
        if vols_edit.text():
            vols = {}
            for v in vols_edit.text().split(','):
                parts = v.strip().split(':')
                if len(parts) == 2:
                    vols[parts[0]] = {'bind': parts[1], 'mode': 'rw'}
            run_args['volumes'] = vols
        if env_edit.text():
            run_args['environment'] = dict(
                e.split('=', 1) for e in env_edit.text().split(',') if '=' in e
            )
        try:
            container = self.docker_client.containers.run(**run_args)
            self.log_message.emit(f"Started container {container.short_id}")
        except Exception as e:
            self.log_message.emit(f"Error: {e}")


# ---------------------------------------------------------------------------
# Volumes view
# ---------------------------------------------------------------------------

class VolumesView(QWidget):
    log_message = pyqtSignal(str)

    def __init__(self, docker_client, logger):
        super().__init__()
        self.docker_client = docker_client
        self.logger = logger
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        for label, func in [("＋  Create Volume", self._create), ("🧹  Prune Unused", self._prune)]:
            btn = QPushButton(label)
            btn.setStyleSheet(TABLE_BTN_STYLE)
            btn.clicked.connect(func)
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Driver", "Mountpoint", "Remove"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setStyleSheet("alternate-background-color: #252526;")
        layout.addWidget(self.table, 1)

    def refresh(self):
        try:
            volumes = self.docker_client.volumes.list()
        except Exception as e:
            self.log_message.emit(f"Error listing volumes: {e}")
            return
        self.table.setRowCount(len(volumes))
        for row, vol in enumerate(volumes):
            self.table.setItem(row, 0, QTableWidgetItem(vol.name))
            self.table.setItem(row, 1, QTableWidgetItem(vol.attrs.get('Driver', '')))
            self.table.setItem(row, 2, QTableWidgetItem(vol.attrs.get('Mountpoint', '')))
            btn = QPushButton("Remove")
            btn.setStyleSheet(DANGER_BTN_STYLE)
            btn.clicked.connect(lambda _, v=vol: self._remove(v))
            self.table.setCellWidget(row, 3, btn)

    def _create(self):
        name, ok = QInputDialog.getText(self, "Create Volume", "Volume name:")
        if ok and name:
            try:
                self.docker_client.volumes.create(name=name)
                self.log_message.emit(f"Volume created: {name}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error: {e}")

    def _prune(self):
        reply = QMessageBox.question(
            self, 'Prune Volumes', "Remove all unused volumes?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                result = self.docker_client.volumes.prune()
                self.log_message.emit(f"Pruned volumes: {result}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error: {e}")

    def _remove(self, vol):
        reply = QMessageBox.question(
            self, 'Remove Volume', f"Remove volume '{vol.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                vol.remove()
                self.log_message.emit(f"Removed volume: {vol.name}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error: {e}")


# ---------------------------------------------------------------------------
# Networks view
# ---------------------------------------------------------------------------

class NetworksView(QWidget):
    log_message = pyqtSignal(str)

    def __init__(self, docker_client, logger):
        super().__init__()
        self.docker_client = docker_client
        self.logger = logger
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        btn = QPushButton("＋  Create Network")
        btn.setStyleSheet(TABLE_BTN_STYLE)
        btn.clicked.connect(self._create)
        toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "ID", "Driver", "Scope", "Remove"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setStyleSheet("alternate-background-color: #252526;")
        layout.addWidget(self.table, 1)

    def refresh(self):
        try:
            networks = self.docker_client.networks.list()
        except Exception as e:
            self.log_message.emit(f"Error listing networks: {e}")
            return
        self.table.setRowCount(len(networks))
        for row, net in enumerate(networks):
            self.table.setItem(row, 0, QTableWidgetItem(net.name))
            self.table.setItem(row, 1, QTableWidgetItem(net.short_id))
            self.table.setItem(row, 2, QTableWidgetItem(net.attrs.get('Driver', '')))
            self.table.setItem(row, 3, QTableWidgetItem(net.attrs.get('Scope', '')))
            btn = QPushButton("Remove")
            btn.setStyleSheet(DANGER_BTN_STYLE)
            btn.clicked.connect(lambda _, n=net: self._remove(n))
            self.table.setCellWidget(row, 4, btn)

    def _create(self):
        name, ok = QInputDialog.getText(self, "Create Network", "Network name:")
        if ok and name:
            try:
                self.docker_client.networks.create(name=name, driver="bridge")
                self.log_message.emit(f"Network created: {name}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error: {e}")

    def _remove(self, net):
        reply = QMessageBox.question(
            self, 'Remove Network', f"Remove network '{net.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                net.remove()
                self.log_message.emit(f"Removed network: {net.name}")
                self.refresh()
            except Exception as e:
                self.log_message.emit(f"Error: {e}")



# ---------------------------------------------------------------------------
# Compose thread
# ---------------------------------------------------------------------------

class ComposeThread(QThread):
    output = pyqtSignal(str)
    finished_ok = pyqtSignal()

    def __init__(self, cmd: list[str], cwd: str):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                self.output.emit(line.rstrip())
            proc.wait()
            if proc.returncode == 0:
                self.finished_ok.emit()
            else:
                self.output.emit(f"⚠  Exit code: {proc.returncode}")
        except FileNotFoundError:
            self.output.emit(
                f"❌  Command not found: {self.cmd[0]}\n"
                "   Install: pip install podman-compose  |  sudo pacman -S docker-compose"
            )
        except Exception as e:
            self.output.emit(f"❌  {e}")


# ---------------------------------------------------------------------------
# Compose view
# ---------------------------------------------------------------------------

class ComposeView(QWidget):
    log_message = pyqtSignal(str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.compose_file = None        # currently loaded compose file
        self.compose_cmd = ["docker", "compose"]   # docker | podman-compose
        self._thread = None
        self._setup_ui()

    # ── UI ─────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # ── File selector bar ─────────────────────────────────────────────
        file_row = QHBoxLayout()
        file_row.setSpacing(6)

        self.file_label = QLabel("No compose file loaded")
        self.file_label.setStyleSheet(
            "color: #6a6a6a; background: #1e1e1e; border: 1px solid #3a3a3a;"
            "border-radius: 4px; padding: 4px 8px;"
        )
        file_row.addWidget(self.file_label, 1)

        open_btn = QPushButton("📂  Open")
        open_btn.setStyleSheet(TABLE_BTN_STYLE)
        open_btn.clicked.connect(self._open_file)
        file_row.addWidget(open_btn)

        reload_btn = QPushButton("↺  PS")
        reload_btn.setStyleSheet(TABLE_BTN_STYLE)
        reload_btn.setToolTip("Service status (compose ps)")
        reload_btn.clicked.connect(self.refresh)
        file_row.addWidget(reload_btn)

        layout.addLayout(file_row)

        # ── Main area: service table + output panel ────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: service table + action buttons
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet("background: #252526; border-radius: 4px;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 8, 8)
        ll.setSpacing(4)

        svc_hdr = QLabel("SERVICES")
        svc_hdr.setStyleSheet(
            "color: #6a6a6a; font-size: 10px; font-weight: bold; padding: 4px 0 2px 0;"
        )
        ll.addWidget(svc_hdr)

        self.svc_table = QTableWidget()
        self.svc_table.setColumnCount(2)
        self.svc_table.setHorizontalHeaderLabels(["Name", "Status"])
        self.svc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.svc_table.setAlternatingRowColors(True)
        self.svc_table.verticalHeader().setDefaultSectionSize(28)
        self.svc_table.setStyleSheet("alternate-background-color: #2a2a2a;")
        self.svc_table.setFixedHeight(180)
        ll.addWidget(self.svc_table)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3a3a3a; margin: 4px 0;")
        ll.addWidget(sep)

        act_hdr = QLabel("ACTIONS")
        act_hdr.setStyleSheet(
            "color: #6a6a6a; font-size: 10px; font-weight: bold; padding: 4px 0 2px 0;"
        )
        ll.addWidget(act_hdr)

        actions = [
            ("▶  Up",          self._up),
            ("▶  Up --build",  self._up_build),
            ("■  Down",        self._down),
            ("⟳  Restart",     self._restart),
            ("🔨  Build",      self._build),
            ("⬇  Pull",        self._pull),
            ("📋  Logs",       self._logs),
        ]
        self._action_btns = []
        for label, func in actions:
            btn = QPushButton(label)
            btn.setStyleSheet(ACTION_BTN_STYLE)
            btn.clicked.connect(func)
            btn.setEnabled(False)   # disabled until a file is loaded
            ll.addWidget(btn)
            self._action_btns.append(btn)

        ll.addStretch()
        splitter.addWidget(left)

        # Jobb: output panel
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(2)

        out_hdr = QLabel("OUTPUT")
        out_hdr.setStyleSheet(
            "color: #6a6a6a; font-size: 10px; font-weight: bold; padding: 4px 0;"
        )
        rl.addWidget(out_hdr)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Monospace", 10))
        self.output.setStyleSheet(
            "background: #0d0d0d; color: #c8c8c8;"
            "border: 1px solid #3a3a3a; border-radius: 4px; padding: 6px;"
            "font-family: 'Courier New', monospace; font-size: 12px;"
        )
        rl.addWidget(self.output, 1)

        # Stop gomb
        stop_row = QHBoxLayout()
        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setStyleSheet(DANGER_BTN_STYLE)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_thread)
        stop_row.addStretch()
        stop_row.addWidget(self.stop_btn)
        rl.addLayout(stop_row)

        splitter.addWidget(right)
        splitter.setSizes([220, 680])
        layout.addWidget(splitter, 1)

    # ── File handling ──────────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Compose File", "",
            "Compose files (docker-compose.yml docker-compose.yaml "
            "compose.yml compose.yaml);;All files (*)"
        )
        if path:
            self.compose_file = path
            self.file_label.setText(path)
            self.file_label.setStyleSheet(
                "color: #4ec9b0; background: #1e1e1e; border: 1px solid #3a3a3a;"
                "border-radius: 4px; padding: 4px 8px;"
            )
            for btn in self._action_btns:
                btn.setEnabled(True)
            self.refresh()

    def _cwd(self):
        """Return the directory of the currently loaded compose file."""
        return os.path.dirname(self.compose_file) if self.compose_file else "."

    # Standard compose filenames – auto-detected by all compose tools
    _STANDARD_NAMES = {
        "compose.yml", "compose.yaml",
        "docker-compose.yml", "docker-compose.yaml",
    }

    def _base_cmd(self):
        """
        Return the compose command with an optional -f flag.

        If the filename is a standard name (compose.yaml etc.), we omit -f –
        the cwd setting is sufficient and avoids -f / --file compatibility
        differences between docker compose / podman compose / podman-compose.
        Non-standard filenames use -f basename.
        """
        fname = os.path.basename(self.compose_file)
        if fname in self._STANDARD_NAMES:
            return self.compose_cmd          # cwd is sufficient, no -f needed
        return self.compose_cmd + ["-f", fname]

    # ── Refresh (compose ps) ───────────────────────────────────────────────

    def refresh(self):
        if not self.compose_file:
            return
        try:
            result = subprocess.run(
                self._base_cmd() + ["ps", "--format", "json"],
                cwd=self._cwd(),
                capture_output=True, text=True, timeout=10,
            )
            self._parse_ps(result.stdout)
        except Exception as e:
            self.log_message.emit(f"Compose ps hiba: {e}")

    def _parse_ps(self, raw: str):
        """Parse the output of compose ps --format json."""
        import json
        self.svc_table.setRowCount(0)
        try:
            data = json.loads(raw) if raw.strip() else []
            # Older compose versions return the name under a different key
            for row, svc in enumerate(data):
                name   = svc.get("Service") or svc.get("Name", "?")
                status = svc.get("Status")  or svc.get("State", "?")
                self.svc_table.insertRow(row)
                self.svc_table.setItem(row, 0, QTableWidgetItem(name))
                item = QTableWidgetItem(status)
                color = "#4ec9b0" if "running" in status.lower() else "#f44747"
                item.setForeground(QColor(color))
                self.svc_table.setItem(row, 1, item)
        except Exception:
            pass   # not JSON – harmless, the table simply won't refresh

    # ── Thread management ───────────────────────────────────────────────────

    def _run(self, extra_args: list[str]):
        if not self.compose_file:
            self.log_message.emit("Load a compose file first.")
            return
        if self._thread and self._thread.isRunning():
            self.log_message.emit("An operation is already running.")
            return

        cmd = self._base_cmd() + extra_args
        self.output.append(f"❯ {' '.join(cmd)}\n")
        self._thread = ComposeThread(cmd, self._cwd())
        self._thread.output.connect(self._append_output)
        self._thread.finished_ok.connect(self.refresh)
        self._thread.finished.connect(lambda: self.stop_btn.setEnabled(False))
        self._thread.start()
        self.stop_btn.setEnabled(True)

    def _stop_thread(self):
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self.output.append("\n⏹  Stopped.")
            self.stop_btn.setEnabled(False)

    def _append_output(self, line: str):
        cleaned = ANSI_ESCAPE.sub("", line)
        self.output.append(cleaned)
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()
        # Podman short-name hint
        if "did not resolve to an alias" in line or "unqualified-search registries" in line:
            hint = (
                "\n💡  Tip: Podman requires a fully-qualified registry name in the compose file.\n"
                "    e.g.: image: docker.io/portainer/portainer-ce:alpine\n"
                "    Or add to /etc/containers/registries.conf:\n"
                "      unqualified-search-registries = [\"docker.io\"]"
            )
            self.output.append(hint)

        # podman-docker shim Yunix hiba
        if "unsupported protocol: Yunix" in line or "TTRPC connection" in line:
            hint = (
                "\n💡  This error is caused by an incompatibility between the podman-docker\n"
                "    shim and compose. Fix: switch to the Podman backend in the app,\n"
                "    or install the real Docker Engine:\n"
                "      sudo pacman -S docker docker-compose\n"
                "      sudo systemctl enable --now docker"
            )
            self.output.append(hint)

    # ── Actions ─────────────────────────────────────────────────────────────

    def _up(self):          self._run(["up", "-d"])
    def _up_build(self):    self._run(["up", "-d", "--build"])
    def _down(self):        self._run(["down"])
    def _restart(self):     self._run(["restart"])
    def _build(self):       self._run(["build"])
    def _pull(self):        self._run(["pull"])
    def _logs(self):        self._run(["logs", "--tail=100"])


# ---------------------------------------------------------------------------
# Swarm view
# ---------------------------------------------------------------------------

class SwarmView(QWidget):
    log_message = pyqtSignal(str)

    def __init__(self, swarm_manager, logger):
        super().__init__()
        self.swarm = swarm_manager
        self.logger = logger
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        warning = QLabel(
            "⚠  Docker Swarm operations can be resource-intensive. Proceed with caution."
        )
        warning.setStyleSheet(
            "color: #dcdcaa; background: #3a3000; border: 1px solid #5a5000;"
            "border-radius: 4px; padding: 8px;"
        )
        layout.addWidget(warning)

        for label, func in [
            ("Initialize Swarm", self._init),
            ("Deploy Service…",  self._deploy),
            ("Scale Service…",   self._scale),
            ("View Nodes",       self._nodes),
            ("Leave Swarm",      self._leave),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(ACTION_BTN_STYLE)
            btn.setFixedWidth(220)
            btn.clicked.connect(func)
            layout.addWidget(btn)

        layout.addStretch()

    def refresh(self):
        pass  # Swarm state shown via log

    def _init(self):
        result = self.swarm.initialize_swarm()
        self.log_message.emit(result)

    def _deploy(self):
        svc, ok1 = QInputDialog.getText(self, "Deploy Service", "Service name:")
        if not ok1 or not svc:
            return
        img, ok2 = QInputDialog.getText(self, "Deploy Service", "Image name:")
        if not ok2 or not img:
            return
        result = self.swarm.deploy_service(svc, img)
        self.log_message.emit(result)

    def _scale(self):
        svc, ok1 = QInputDialog.getText(self, "Scale Service", "Service name:")
        if not ok1 or not svc:
            return
        reps, ok2 = QInputDialog.getText(self, "Scale Service", "Number of replicas:")
        if not ok2 or not reps:
            return
        result = self.swarm.scale_service(svc, reps)
        self.log_message.emit(result)

    def _nodes(self):
        result = self.swarm.view_nodes()
        self.log_message.emit(result)

    def _leave(self):
        reply = QMessageBox.question(
            self, 'Leave Swarm', "Are you sure you want to leave the Swarm?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            result = self.swarm.leave_swarm()
            self.log_message.emit(result)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class DockerGui(QWidget):
    def __init__(self):
        super().__init__()
        self.logger = Logger()
        self.current_backend = "Docker"       # "Docker" | "Podman"
        self.podman_caps = None               # PodmanCapabilities | None
        self._connect_docker()
        self.swarm = SwarmManager(self.logger)
        self._setup_ui()
        self._setup_refresh_timer()

    def _connect_docker(self):
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            self.docker_client = None
            print(f"Docker connection failed: {e}")

    def _setup_ui(self):
        self.setWindowTitle("Docker Manager")
        self.setMinimumSize(900, 650)
        self.setStyleSheet(DARK_THEME)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ────────────────────────────────────────────────────────
        top_bar = QWidget()
        top_bar.setFixedHeight(46)
        top_bar.setStyleSheet("background: #141414; border-bottom: 1px solid #3a3a3a;")
        top_row = QHBoxLayout(top_bar)
        top_row.setContentsMargins(14, 0, 14, 0)

        self.title_label = QLabel("🐋  Docker Manager")
        self.title_label.setStyleSheet("color: #4fc3f7; font-size: 15px; font-weight: bold;")
        top_row.addWidget(self.title_label)

        # Backend badge – shown when using Podman
        self.backend_badge = QLabel()
        self.backend_badge.setStyleSheet(
            "color: #a277ff; background: #2a1a3a; border: 1px solid #a277ff;"
            "border-radius: 3px; padding: 1px 7px; font-size: 11px; font-weight: bold;"
        )
        self.backend_badge.hide()
        top_row.addWidget(self.backend_badge)

        top_row.addStretch()

        top_row.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Docker")
        podman_item = "Podman" if is_podman_available() else "Podman (not installed)"
        self.backend_combo.addItem(podman_item)
        if not is_podman_available():
            # Disable the Podman option if it is not installed
            from PyQt5.QtGui import QStandardItemModel
            model = self.backend_combo.model()
            item = model.item(1)
            item.setEnabled(False)
            item.setToolTip("The 'podman' binary was not found in PATH.")
        self.backend_combo.currentTextChanged.connect(self._switch_backend)
        top_row.addWidget(self.backend_combo)

        root.addWidget(top_bar)

        # ── Nav bar ────────────────────────────────────────────────────────
        nav_bar = QWidget()
        nav_bar.setFixedHeight(40)
        nav_bar.setStyleSheet("background: #1a1a1a; border-bottom: 1px solid #3a3a3a;")
        nav_row = QHBoxLayout(nav_bar)
        nav_row.setContentsMargins(8, 0, 8, 0)
        nav_row.setSpacing(0)

        self.nav_buttons = []
        for i, label in enumerate(["Containers", "Images", "Volumes", "Networks", "Swarm", "Compose"]):
            btn = QPushButton(label)
            btn.setStyleSheet(NAV_BTN_STYLE)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, idx=i: self._switch_view(idx))
            nav_row.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_row.addStretch()
        root.addWidget(nav_bar)

        # ── Content (stacked) ──────────────────────────────────────────────
        self.stack = QStackedWidget()

        self.containers_view = ContainersView(self.docker_client, self.logger)
        self.images_view = ImagesView(self.docker_client, self.logger)
        self.volumes_view = VolumesView(self.docker_client, self.logger)
        self.networks_view = NetworksView(self.docker_client, self.logger)
        self.swarm_view = SwarmView(self.swarm, self.logger)
        self.compose_view = ComposeView(self.logger)

        for view in [
            self.containers_view, self.images_view,
            self.volumes_view, self.networks_view, self.swarm_view,
            self.compose_view,
        ]:
            view.log_message.connect(self._append_log)
            self.stack.addWidget(view)

        root.addWidget(self.stack, 1)

        # ── Log area ───────────────────────────────────────────────────────
        log_frame = QWidget()
        log_frame.setFixedHeight(130)
        log_frame.setStyleSheet("background: #141414; border-top: 1px solid #3a3a3a;")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(8, 4, 8, 4)
        log_layout.setSpacing(2)

        log_header = QLabel("LOG OUTPUT")
        log_header.setStyleSheet(
            "color: #6a6a6a; font-size: 10px; font-weight: bold;"
        )
        log_layout.addWidget(log_header)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont('Monospace', 9))
        self.log_output.setStyleSheet(
            "background: #0d0d0d; color: #9cdcfe; border: none;"
            "font-family: 'Courier New', monospace;"
        )
        log_layout.addWidget(self.log_output)
        root.addWidget(log_frame)

        # Start on Containers tab
        self._switch_view(0)

    def _switch_view(self, index):
        # Swarm (index=4) is not available under Podman
        swarm_btn = self.nav_buttons[4]
        if self.current_backend == "Podman":
            swarm_btn.setEnabled(False)
            swarm_btn.setToolTip("Docker Swarm is not supported under Podman.")
            if index == 4:
                index = 0   # fall back to Containers tab
        else:
            swarm_btn.setEnabled(True)
            swarm_btn.setToolTip("")

        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)
        views = [
            self.containers_view, self.images_view,
            self.volumes_view, self.networks_view, self.swarm_view,
            self.compose_view,
        ]
        views[index].refresh()

    def _switch_backend(self, backend_text: str):
        # The combo text may also be "Podman (not installed)"
        backend = "Podman" if backend_text.startswith("Podman") else "Docker"

        if backend == self.current_backend:
            return

        if backend == "Docker":
            try:
                self.docker_client = docker.from_env()
                self.current_backend = "Docker"
                self.podman_caps = None
                self.containers_view.podman_caps = None
                self.containers_view.shell.binary = "docker"
                self.compose_view.compose_cmd = ["docker", "compose"]
                self._apply_backend_ui("Docker")
                for view in [self.containers_view, self.images_view,
                              self.volumes_view, self.networks_view]:
                    view.docker_client = self.docker_client
                self._append_log("Backend: Docker")
                self._switch_view(self.stack.currentIndex())
            except Exception as e:
                self._append_log(f"Docker connection failed: {e}")

        elif backend == "Podman":
            try:
                client, caps = get_podman_client()
                self.docker_client = client
                self.current_backend = "Podman"
                self.podman_caps = caps
                self._apply_backend_ui("Podman", caps)
                for view in [self.containers_view, self.images_view,
                              self.volumes_view, self.networks_view]:
                    view.docker_client = self.docker_client
                # Log known limitations
                self._append_log(
                    f"Backend: Podman  v{caps.server_version}  API {caps.api_version}"
                )
                for warn in caps.warnings():
                    self._append_log(f"⚠  {warn}")
                self.containers_view.podman_caps = caps
                self.containers_view.shell.binary = "podman"
                import shutil
                if shutil.which("podman-compose"):
                    self.compose_view.compose_cmd = ["podman-compose"]
                else:
                    self.compose_view.compose_cmd = ["podman", "compose"]
                self._switch_view(self.stack.currentIndex())
            except ConnectionError as e:
                self._append_log(f"Podman connection failed:\n{e}")
                # Revert the combo back to Docker
                self.backend_combo.blockSignals(True)
                self.backend_combo.setCurrentIndex(0)
                self.backend_combo.blockSignals(False)
            except Exception as e:
                self._append_log(f"Podman hiba: {e}")
                self.backend_combo.blockSignals(True)
                self.backend_combo.setCurrentIndex(0)
                self.backend_combo.blockSignals(False)

    def _apply_backend_ui(self, backend: str, caps: "PodmanCapabilities | None" = None):
        """Update the header badge and window title for the selected backend."""
        if backend == "Podman":
            ver = caps.server_version if caps else "?"
            self.backend_badge.setText(f"Podman {ver}")
            self.backend_badge.show()
            self.title_label.setText("🦭  Docker Manager")
            self.setWindowTitle("Docker Manager  [Podman]")
        else:
            self.backend_badge.hide()
            self.title_label.setText("🐋  Docker Manager")
            self.setWindowTitle("Docker Manager")

    def _setup_refresh_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._auto_refresh)
        self.timer.start(5000)

    def _auto_refresh(self):
        # Only auto-refresh containers view (button bar)
        if self.stack.currentIndex() == 0:
            self.containers_view.refresh()

    def _append_log(self, message):
        self.log_output.append(message)
        self.logger.log_info(message)

    def closeEvent(self, event):
        self.containers_view.shell.disconnect_shell()
        self.containers_view._stop_resource_monitor()
        # Stop any floating monitor windows so their threads are cleanly joined
        for win, thread in list(self.containers_view.monitor_windows.values()):
            try:
                thread.update_graph.disconnect()
            except Exception:
                pass
            thread.stop()
            thread.wait(1500)
            win.close()
        self.containers_view.monitor_windows.clear()
        event.accept()