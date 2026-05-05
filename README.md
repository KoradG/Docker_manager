# Docker Manager — Technical Documentation

A desktop application for managing Docker and Podman containers through a PyQt5 graphical interface. The application provides container lifecycle management, image and registry operations, volume and network administration, Docker Compose orchestration, Docker Swarm management, real-time resource monitoring with live graphs, and a fully functional VT100/XTERM terminal emulator embedded directly in the UI — all with runtime switching between Docker and Podman backends.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Dependencies](#2-dependencies)
3. [Project Structure](#3-project-structure)
4. [Architecture Overview](#4-architecture-overview)
5. [Module: `main.py`](#5-module-mainpy)
6. [Module: `docker_gui.py`](#6-module-docker_guipy)
   - 6.1 [Global constants and helpers](#61-global-constants-and-helpers)
   - 6.2 [ShellWidget — embedded terminal emulator](#62-shellwidget--embedded-terminal-emulator)
   - 6.3 [PullImageThread](#63-pullimagethread)
   - 6.4 [ContainerButton](#64-containerbutton)
   - 6.5 [ContainersView](#65-containersview)
   - 6.6 [ImagesView](#66-imagesview)
   - 6.7 [VolumesView and NetworksView](#67-volumesview-and-networksview)
   - 6.8 [ComposeView and ComposeThread](#68-composeview-and-composethread)
   - 6.9 [SwarmView](#69-swarmview)
   - 6.10 [DockerGui — main window](#610-dockergui--main-window)
7. [Module: `docker_client.py`](#7-module-docker_clientpy)
8. [Module: `podman_utils.py`](#8-module-podman_utilspy)
9. [Module: `resource_monitor.py`](#9-module-resource_monitorpy)
10. [Module: `swarm.py`](#10-module-swarmpy)
11. [Module: `logs.py`](#11-module-logspy)
12. [Module: `terminal_utils.py`](#12-module-terminal_utilspy)
13. [Threading Model](#13-threading-model)
14. [Signal / Slot Map](#14-signal--slot-map)
15. [Known Limitations](#15-known-limitations)

---

## 1. Getting Started

> The application is developed and tested on Linux. Windows and macOS are partially supported — the terminal emulator and PTY subsystem require a POSIX environment.

```bash
# Install Python dependencies
pip install -r requirements.txt

# Optional: add your user to the docker group (avoids sudo)
sudo usermod -aG docker $USER
newgrp docker   # apply without logging out

# Launch
python main.py
```

### Podman backend

The Podman socket must be running before switching to the Podman backend in the UI:

```bash
systemctl --user start podman.socket
# Enable permanently:
systemctl --user enable --now podman.socket
```

**Image names in compose files** must be fully qualified when using Podman, because Podman does not implicitly resolve short names to `docker.io`:

```yaml
# Wrong (works on Docker, fails on Podman):
image: postgres:16-alpine

# Correct (works on both):
image: docker.io/library/postgres:16-alpine
```

Alternatively, add to `/etc/containers/registries.conf`:

```toml
unqualified-search-registries = ["docker.io"]
```

---

## 2. Dependencies

### System

| Dependency | Required | Purpose |
|---|---|---|
| Docker Engine | Yes (or Podman) | Container daemon |
| `docker compose` plugin or `docker-compose` | Recommended | Compose view |
| `podman` + `podman-compose` or `podman compose` | Optional | Podman backend |

### Python

| Package | Version | Used in | Purpose |
|---|---|---|---|
| `docker` | 7.1.0 | `docker_gui.py`, `docker_client.py`, `resource_monitor.py` | Official Docker Python SDK |
| `PyQt5` | 5.15.11 | `docker_gui.py`, `resource_monitor.py`, `main.py` | GUI framework |
| `matplotlib` | ≥ 3.7.0 | `resource_monitor.py` | Real-time resource graphs |
| `pyte` | ≥ 0.8.0 | `docker_gui.py` | VT100/XTERM terminal state machine |
| `requests` | 2.32.3 | `docker_gui.py` | HTTP utilities |
| `PyYAML` | 6.0.2 | `docker_gui.py` | YAML parsing |

All other imports (`os`, `re`, `subprocess`, `socket`, `pty`, `fcntl`, `termios`, `struct`, `platform`, `shutil`, `logging`, `traceback`, `collections`, `time`, `threading`, `json`) are from the Python standard library.

---

## 3. Project Structure

```
main.py               # Entry point
docker_gui.py         # Complete GUI: 15 classes, ~2100 lines
docker_client.py      # DockerClient — typed wrapper around the Docker SDK
podman_utils.py       # Podman socket detection and capability probing
resource_monitor.py   # ResourceMonitorThread + ResourceGraphWidget
swarm.py              # SwarmManager — Swarm CLI wrapper
logs.py               # Logger — file-based logging
terminal_utils.py     # Cross-platform terminal emulator detection and launch
requirements.txt      # Python package manifest
```

---

## 4. Architecture Overview

The application follows a single-process, multi-threaded architecture built on Qt's event loop. All UI updates happen on the main thread. Background work (container stats polling, image pulls, compose subprocess streaming) runs in `QThread` subclasses and communicates with the main thread exclusively via Qt signals.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Main thread (Qt event loop)                                        │
│                                                                     │
│  DockerGui                                                          │
│  ├── ContainersView                                                 │
│  │   ├── ShellWidget  ──────── QSocketNotifier ──► PTY master fd   │
│  │   └── ResourceMonitorThread (QThread)  ──signal──► progress bars│
│  ├── ImagesView                                                     │
│  │   └── PullImageThread (QThread)  ──signal──► QProgressDialog    │
│  ├── VolumesView                                                    │
│  ├── NetworksView                                                   │
│  ├── ComposeView                                                    │
│  │   └── ComposeThread (QThread)  ──signal──► output panel         │
│  └── SwarmView                                                      │
│                                                                     │
│  Docker Python SDK  ──unix socket──►  Docker / Podman daemon        │
└─────────────────────────────────────────────────────────────────────┘
```

The Docker SDK communicates with the daemon over the Unix socket (`/var/run/docker.sock` for Docker, `/run/user/<uid>/podman/podman.sock` for rootless Podman). All SDK calls are synchronous and made from the main thread, except inside `ResourceMonitorThread` which calls `container.stats()` from its own thread.

Backend switching (Docker ↔ Podman) is non-destructive: a new SDK client is created and assigned to all views while the UI remains open. The shell widget reconnects to the selected container automatically.

---

## 5. Module: `main.py`

```python
signal.signal(signal.SIGINT, signal.SIG_IGN)
```

Before entering the Qt event loop, `SIGINT` is suppressed at the process level. This is necessary because `ShellWidget` forwards `Ctrl+C` (`\x03`) through the PTY to the container's bash. Without this, a race condition could deliver `SIGINT` to the Python process itself and kill the application. With `SIG_IGN`, the signal is silently discarded at the OS level and only the PTY path (which delivers it to bash inside the container) takes effect.

After that, a `QApplication` is created and `DockerGui` is shown. `sys.exit(app.exec_())` enters the event loop and forwards Qt's exit code to the OS.

---

## 6. Module: `docker_gui.py`

### 6.1 Global constants and helpers

#### Stylesheet constants

Six module-level QSS string constants define the visual theme. QSS (Qt Style Sheets) uses CSS-like syntax applied to widget trees. Setting a stylesheet on a parent widget cascades to all children unless overridden.

| Constant | Widget targets | Key properties |
|---|---|---|
| `DARK_THEME` | Root `DockerGui` | Background `#1e1e1e`, text `#d4d4d4`, focus border `#007acc`, selection `#264f78` |
| `NAV_BTN_STYLE` | Navigation tab buttons | Transparent background; active tab: `color: #4fc3f7`, `border-bottom: 2px solid #4fc3f7` |
| `ACTION_BTN_STYLE` | Left-panel action buttons | Background `#2a2a2a`, left-aligned text, hover border `#007acc` |
| `MONITOR_BTN_STYLE` | "Open Monitor" button | Blue tint to visually separate from action buttons |
| `TABLE_BTN_STYLE` | In-table action buttons | Compact padding, `#9cdcfe` text |
| `DANGER_BTN_STYLE` | Remove/destructive buttons | Dark red background `#3a1a1a`, red text `#f44747` |

#### `ANSI_ESCAPE`

```python
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
```

Compiled regex for stripping ANSI escape sequences. Retained in the module for any legacy text-processing paths, though `ShellWidget` no longer uses it (pyte handles escape sequences natively).

#### `_ANSI_COLORS`

A dict mapping pyte's named colour strings to `QColor` values. pyte returns colour names as strings from the set: `'black'`, `'red'`, `'green'`, `'brown'` (dark yellow), `'blue'`, `'magenta'`, `'cyan'`, `'white'`, and their `'bright'`-prefixed variants. The colour values are chosen to match VS Code's dark theme palette for visual consistency.

#### `_256_color(n: int) -> QColor`

Converts a 256-colour palette index to `QColor`. The 256-colour palette is structured as three zones:

- **0–15**: Standard ANSI 16 colours — delegated to `_ANSI_COLORS`.
- **16–231**: A 6×6×6 RGB cube. Index `n` (after subtracting 16) encodes red, green, and blue as `r = n // 36`, `g = (n // 6) % 6`, `b = n % 6`, each mapped to the range `{0, 95, 135, 175, 215, 255}` by the formula `0 if x == 0 else 55 + x * 40`.
- **232–255**: A uniform greyscale ramp from near-black to near-white: `value = 8 + (n - 232) * 10`.

Note: pyte 0.8.x returns 256-colour values as 6-character lowercase hex strings without a `#` prefix (e.g. `'ff00d7'`), not as integers. The `_color()` method in `ShellWidget` handles this format directly and does not call `_256_color`.

#### `_KEY_MAP`

Maps Qt key constants to terminal escape byte sequences. The full mapping:

| Key | Sequence |
|---|---|
| Return / Enter | `\r` |
| Backspace | `\x7f` (DEL, the standard terminal erase character) |
| Tab | `\t` |
| Escape | `\x1b` |
| Up / Down / Right / Left | `\x1b[A` / `\x1b[B` / `\x1b[C` / `\x1b[D` |
| Home / End | `\x1b[H` / `\x1b[F` |
| PageUp / PageDown | `\x1b[5~` / `\x1b[6~` |
| Delete | `\x1b[3~` |
| Insert | `\x1b[2~` |
| F1–F4 | `\x1bOP` – `\x1bOS` (SS3 sequences) |
| F5–F12 | `\x1b[15~` – `\x1b[24~` (skipping 16) |

---

### 6.2 `ShellWidget` — embedded terminal emulator

`ShellWidget` is the most technically complex component in the application. It implements a complete VT100/XTERM terminal emulator inside a `QWidget`, providing interactive shell access to running containers without opening an external terminal window.

#### Design rationale

Earlier iterations used `QTextEdit` with `subprocess.Popen` piped I/O. This approach worked for simple command output but failed for TUI applications (`htop`, `vim`, `nano`, `less`, `man`) because:

1. These applications use ANSI escape sequences for cursor positioning, colour, and screen clearing — which `QTextEdit` renders as literal text.
2. They query the terminal for its size via `TIOCGWINSZ` — which pipes do not support.
3. They require a PTY to enable line-discipline features (echo, signal generation, raw mode).

The current implementation replaces `QTextEdit` with a fully custom `QPainter`-based widget backed by `pyte.HistoryScreen`, connected to a real PTY.

#### State

```python
self.binary        # "docker" | "podman" — set by DockerGui on backend switch
self.process       # subprocess.Popen — the running docker/podman exec process
self.master_fd     # int — PTY master file descriptor
self.notifier      # QSocketNotifier — fires when data is available on master_fd
self._connected    # bool — controls paintEvent rendering mode
self._scroll_offset  # int — 0 = live view, N = N lines scrolled into history
self._font         # QFont("Monospace", 11)
self._cw, self._ch # int — pixel width/height of a single character cell
self._cols, self._rows  # int — terminal dimensions in characters
self._screen       # pyte.HistoryScreen
self._stream       # pyte.Stream — feeds raw bytes into _screen
```

#### PTY setup (`connect_container`)

```
pty.openpty()
    │
    ├── master_fd  ←→  our process (reads output, writes input)
    └── slave_fd   ←→  docker exec process (its stdin/stdout/stderr)
```

1. `pty.openpty()` calls the `openpty(3)` C library function, which creates a linked PTY master/slave pair via `/dev/ptmx`. The kernel PTY layer sits between them, implementing the POSIX terminal line discipline.

2. **ISIG is disabled on the slave** via `termios.tcgetattr` / `tcsetattr`:

   ```python
   attrs = termios.tcgetattr(slave_fd)
   attrs[3] &= ~(termios.ISIG | termios.IXON)
   termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
   ```

   `attrs[3]` is `c_lflag` (local mode flags). `ISIG` controls whether special characters (`\x03` = INTR, `\x1c` = QUIT, `\x1a` = SUSP) generate signals for the process group attached to the slave. `IXON` controls XON/XOFF software flow control.

   **Why this matters:** With `ISIG` enabled (the default), writing `\x03` to the master fd triggers the kernel PTY layer to deliver `SIGINT` to the *foreground process group of the slave* — which is `docker exec`. `docker exec` terminates on `SIGINT`, dropping the connection. This is the root cause of Ctrl+C killing the entire shell session rather than interrupting only the running command.

   With `ISIG` disabled, `\x03` is treated as a plain data byte. It flows through `docker exec` (which just proxies its stdin to the container's PTY) to the container's internal PTY, where bash's own line discipline has `ISIG` enabled and correctly delivers `SIGINT` to the foreground process group of bash. The running command is interrupted; bash survives.

   `IXON` is also cleared to prevent `\x13` (Ctrl+S) from suspending output via XON/XOFF flow control at the host PTY level.

3. `TIOCSWINSZ` is sent to synchronise the terminal dimensions:

   ```python
   fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
               struct.pack('HHHH', rows, cols, 0, 0))
   ```

   The `struct` packs four `unsigned short` values: rows, columns, pixel width (unused), pixel height (unused). This ioctl propagates `SIGWINCH` to the process group attached to the slave, causing `docker exec` to resize its internal PTY and `bash` (and any running TUI application) to re-render.

4. `subprocess.Popen` launches `docker exec -it <id> /bin/sh -c 'bash 2>/dev/null || sh'` with `stdin`, `stdout`, and `stderr` all set to `slave_fd`. `close_fds=True` ensures all other file descriptors in the parent are closed in the child. After `Popen` returns, the parent calls `os.close(slave_fd)` — the child has its own copy and the parent no longer needs it.

5. A `QSocketNotifier` is attached to `master_fd` with `QSocketNotifier.Read`. Qt integrates this into its GLib event loop: whenever data becomes available on the file descriptor, `activated` fires on the main thread and `_read_output` is called.

#### Terminal dimensions (`resizeEvent`)

```python
new_cols = max(self.width()  // self._cw, 10)
new_rows = max(self.height() // self._ch,  5)
```

Cell dimensions `_cw` and `_ch` are computed once from `QFontMetrics.horizontalAdvance('M')` and `QFontMetrics.height()` respectively (using the character `'M'` as a representative wide character for monospace width). On every resize, if the dimensions change, `pyte.Screen.resize(rows, cols)` is called to reflow the pyte buffer, and `TIOCSWINSZ` is sent to the PTY.

#### Scrollback (`pyte.HistoryScreen`)

`pyte.HistoryScreen` extends the standard `pyte.Screen` with a history buffer. When a line scrolls off the top of the visible area (because a new line is added at the bottom of a full screen), it is pushed into `screen.history.top`, a `collections.deque` capped at `_HISTORY = 2000` entries. Each entry is a dict mapping column index (int) to `pyte.Char` namedtuples.

`_get_display_lines()` constructs the list of lines to render:

```python
if self._scroll_offset == 0:
    return [self._screen.buffer[r] for r in range(self._rows)]

history = list(self._screen.history.top)
n_hist  = len(history)
total   = n_hist + self._rows
end     = total - self._scroll_offset
start   = max(0, end - self._rows)
# slice [start:end] from the combined history+buffer tape
```

The "tape" is conceptually `history.top[0..n_hist-1]` (oldest to newest) concatenated with `buffer[0..rows-1]`. With `_scroll_offset = 0`, only the live buffer is shown. With `_scroll_offset = N`, the window is shifted N lines toward the past. Padding empty dicts are inserted at the top if `start` reaches below the oldest history entry.

`_scroll_by(lines)` updates `_scroll_offset` clamped to `[0, _max_scroll()]` and calls `self.update()` to schedule a repaint.

Scroll position stability during live output: `_read_output` tracks how many lines were pushed to history before and after `_stream.feed(data)`. If the user is scrolled up, `_scroll_offset` is incremented by the number of newly pushed lines, keeping the same historical content in view.

#### Rendering (`paintEvent`)

`paintEvent` is called by Qt whenever the widget needs repainting (after `self.update()` or a window expose event). `WA_OpaquePaintEvent` is set, telling Qt that every pixel will be painted and no background erase is needed before the call — this eliminates a flicker-inducing intermediate clear.

The render loop:

```python
for row, line in enumerate(lines):
    for col in range(self._cols):
        char = line.get(col)       # pyte.Char namedtuple, or None for empty cell
        if char is None: continue

        fg = self._color(char.fg, fg=True)
        bg = self._color(char.bg, fg=False)
        if char.reverse: fg, bg = bg, fg

        is_cursor = (col == cursor_x and row == cursor_y)
        x, y = col * self._cw, row * self._ch

        # 1. Background fill (skip if default colour and not cursor cell)
        cell_bg = self._CURSOR_COL if is_cursor else bg
        if cell_bg != self._DEFAULT_BG:
            painter.fillRect(x, y, self._cw, self._ch, cell_bg)

        # 2. Glyph (skip spaces)
        if glyph := char.data and char.data != ' ':
            if char.bold: painter.setFont(bold_font)
            painter.setPen(self._DEFAULT_BG if is_cursor else fg)
            painter.drawText(x, y, self._cw, self._ch,
                             Qt.AlignLeft | Qt.AlignVCenter, glyph)

        # 3. Underline decoration
        if char.underscore:
            painter.drawLine(x, y + self._ch - 2, x + self._cw - 1, y + self._ch - 2)
```

`_color(val, fg)` resolves a pyte colour value to `QColor`:
- `'default'` or empty → `_DEFAULT_FG` / `_DEFAULT_BG`
- Named colour (e.g. `'red'`, `'brightblue'`) → lookup in `_ANSI_COLORS`
- 6-character hex string (e.g. `'ff00d7'`) → `QColor('#' + val)` — this is the format pyte uses for 256-colour and truecolour values

The cursor is hidden when `_scroll_offset > 0` (the live cursor position is not meaningful when viewing history).

**Scroll indicator:** A 3-pixel-wide bar is drawn on the right edge of the widget when scrolled. The thumb position and height are computed proportionally:

```python
ratio   = _scroll_offset / _max_scroll()
thumb_h = max(20, bar_h * rows / (max_scroll + rows))
thumb_y = (bar_h - thumb_h) * (1.0 - ratio)
```

#### Keyboard handling (`keyPressEvent`)

```
event.key()  →  _KEY_MAP  →  byte sequence
                   ↓ (miss)
             Ctrl modifier?  →  bytes([key - Qt.Key_A + 1])
                   ↓ (no)
             event.text().encode('utf-8')
```

Control characters are derived from the Qt key constant directly: `bytes([key - Qt.Key_A + 1])`. For `Qt.Key_C` (= 67 = ord('C')), this gives `bytes([3])` = `\x03`. This approach is immune to the `event.text()` empty-string issue that occurs on some Qt/Linux configurations where `Ctrl+letter` does not populate the text field.

`event.accept()` is called after every handled key to prevent propagation up the widget hierarchy. Without this, Qt's shortcut system could intercept control sequences and trigger unintended application-level actions.

`Shift+PageUp` / `Shift+PageDown` are handled first (before the `master_fd is None` guard) so scrollback works even when disconnected.

#### Session persistence

```python
# In ContainersView.select_container, on switching away from a container:
self.shell_sessions[prev_id] = {
    'screen':    self.shell._screen,     # pyte.HistoryScreen object
    'process':   self.shell.process,     # Popen instance
    'master_fd': self.shell.master_fd,   # PTY master fd (int)
}
self.shell._detach()   # stops QSocketNotifier, leaves process/PTY alive

# On switching back:
self.shell._reattach(session['process'], session['master_fd'],
                     session['screen'], container.name)
```

`_detach()` only stops the `QSocketNotifier`. The PTY master fd remains open, the subprocess remains running, and the pyte screen object retains its state (including all 2000 history lines). When `_reattach()` is called, the screen is restored, a new `pyte.Stream` is created for it, and the notifier is restarted. Any output that accumulated in the PTY kernel buffer during the detached period is immediately consumed and fed to pyte, updating the screen to the current state.

`_push_pty_size()` is called after reattach to resynchronise the terminal dimensions. This sends `SIGWINCH` to the process group, causing bash (and any running application) to redraw.

---

### 6.3 `PullImageThread`

Subclasses `QThread` to pull an image in the background. Uses `client.api.pull(repository, stream=True, decode=True)` — the low-level API call that streams JSON chunks rather than blocking. Each chunk is decoded and a progress message is emitted via the `progress(str)` signal, optionally including a percentage derived from `progressDetail.current / progressDetail.total`.

The thread is created fresh for each pull; there is no thread pool. The `QProgressDialog` on the main thread is kept alive by connecting `finished` to `progress.close`.

---

### 6.4 `ContainerButton`

A `QPushButton` subclass that is checkable (acts as a radio button within the button bar). Style is applied in `_apply_style()` using a format-string QSS with status-specific colours. The `container` attribute holds the most recent container object as of the last `refresh()`.

---

### 6.5 `ContainersView`

The main container management view. Key design points:

**`_switching` guard:** `select_container` sets `self._switching = True` at entry and `False` in a `finally` block. `refresh()` returns immediately if `_switching` is True. This prevents the 5-second auto-refresh timer from triggering a `refresh()` in the middle of a container switch, which would rebuild all buttons and potentially lose the selection state or cause a use-after-free on the pyte screen object.

**Resource monitor lifecycle:**

`_start_resource_monitor(container)` creates a fresh `ResourceMonitorThread`, connects its `update_graph` signal to `_update_resources`, and starts it. `_stop_resource_monitor()` disconnects the signal, calls `thread.stop()` (sets `_running = False`), then `thread.wait(1500)`. The `wait(1500)` is critical: without it, setting `self.resource_thread = None` releases the last Python reference to the `QThread` subclass instance. Python's garbage collector then calls the object's destructor, which calls `QThread::~QThread()`. Qt's implementation of this destructor calls `qFatal()` if the thread is still running — this aborts the process with `SIGABRT`. The 1500 ms timeout is chosen to exceed the 1-second `time.sleep` in the thread's polling loop, ensuring it will always exit within the window.

**Floating monitor windows:** `open_monitor(container)` creates a standalone `QWidget` window containing a `ResourceGraphWidget` and an independent `ResourceMonitorThread`. The window and thread are stored in `monitor_windows[container.id]`. The `on_close` handler for the window calls `thread.stop()` and `thread.wait(1500)` before accepting the close event. On container removal (`remove_container`), any associated monitor window is cleaned up via `monitor_windows.pop(c.id)`. On application exit, `DockerGui.closeEvent` iterates all remaining entries in `monitor_windows` and joins each thread.

**`_get_selected()`:** Always re-fetches the container object from the daemon via `docker_client.containers.get(id)` rather than returning the cached button object. This ensures the returned container reflects the true current state.

---

### 6.6 `ImagesView`

**Run with params dialog:** The `QFormLayout` dialog collects:

| Field | Widget | Docker API parameter |
|---|---|---|
| CPUs | `QSpinBox` 1–32 | `cpu_quota = value * 100000`, `cpu_period = 100000` |
| Memory (MB) | `QSpinBox` 64–32768 | `mem_limit = f"{value}m"` |
| Command | `QLineEdit` | `command` kwarg |
| Ports | `QLineEdit` `host:container,...` | `ports = {container_port: host_port, ...}` |
| Volumes | `QLineEdit` `host:container,...` | `volumes = {host: {'bind': container, 'mode': 'rw'}}` |
| Env vars | `QLineEdit` `KEY=VALUE,...` | `environment = {'KEY': 'VALUE', ...}` |
| Restart policy | `QComboBox` | `restart_policy = {'Name': value}` |

All fields except CPUs and Memory are optional. The assembled `kwargs` dict is passed directly to `docker_client.containers.run(**run_args)`.

---

### 6.7 `VolumesView` and `NetworksView`

Both follow the same pattern: a toolbar with creation actions, a `QTableWidget` with one row per resource, and a per-row Remove button with a `QMessageBox` confirmation dialog. `VolumesView` additionally has a Prune button that calls `docker_client.volumes.prune()`. `NetworksView` creates networks with `driver="bridge"` by default.

---

### 6.8 `ComposeView` and `ComposeThread`

**Compose command selection:** `self.compose_cmd` is a list set by `DockerGui._switch_backend`:

| Backend | Condition | `compose_cmd` |
|---|---|---|
| Docker | Default | `["docker", "compose"]` |
| Podman | `podman-compose` found on PATH | `["podman-compose"]` |
| Podman | only `podman compose` available | `["podman", "compose"]` |

**`_base_cmd()`** determines whether to append `-f <filename>` to the compose command. If the loaded filename matches one of the four standard names (`compose.yml`, `compose.yaml`, `docker-compose.yml`, `docker-compose.yaml`), the flag is omitted — the working directory alone is sufficient, and this avoids a subtle incompatibility: `podman-compose` and `docker compose` differ slightly in how they handle `-f` relative paths.

**`_parse_ps(raw)`** parses JSON from `compose ps --format json`. The JSON structure varies between compose tool versions: the service name may be under `"Service"` (newer) or `"Name"` (older), and status under `"Status"` or `"State"`. Both variants are handled with `.get()` fallbacks.

**`ComposeThread.run()`** streams stdout line by line from a `subprocess.Popen`. On exit code != 0, the code is emitted as a warning. On `FileNotFoundError` (compose binary not found), a helpful installation hint is emitted. Two Podman-specific error patterns are detected in `_append_output`:

- `"did not resolve to an alias"` / `"unqualified-search-registries"` → hint to use fully-qualified image names.
- `"unsupported protocol: Yunix"` / `"TTRPC connection"` → hint about the podman-docker shim incompatibility.

---

### 6.9 `SwarmView`

All Swarm operations delegate to `SwarmManager` (see §10). The Swarm tab is disabled when the Podman backend is active (`_switch_view` checks `current_backend == "Podman"` and redirects index 4 back to 0).

---

### 6.10 `DockerGui` — main window

**Layout:**

```
┌─ top bar (46px) ──────────────────────────────────────────┐
│  🐋 Docker Manager  [Podman badge]    Backend: [Docker ▾] │
├─ nav bar (40px) ──────────────────────────────────────────┤
│  Containers  Images  Volumes  Networks  Swarm  Compose    │
├─ QStackedWidget (stretch) ────────────────────────────────┤
│  (active view)                                            │
├─ log panel (130px) ───────────────────────────────────────┤
│  LOG OUTPUT                                               │
│  [QTextEdit, read-only, monospace]                        │
└───────────────────────────────────────────────────────────┘
```

**`_switch_view(index)`** updates `nav_buttons[i].setChecked`, sets `stack.currentIndex`, and calls `views[index].refresh()` — ensuring the newly visible view always shows current data.

**`_switch_backend(backend_text)`** is connected to `backend_combo.currentTextChanged`. The text is normalised: any text starting with `"Podman"` (including `"Podman (not installed)"`) maps to the `"Podman"` branch. The combo item for Podman is disabled via `QStandardItemModel.item(1).setEnabled(False)` when `is_podman_available()` returns False.

On switch to Podman: `get_podman_client()` is called; on `ConnectionError`, the log panel shows the error and `blockSignals(True)` prevents the signal from firing while the combo is reset to index 0. On success, each view's `docker_client` attribute is updated, `ContainersView.podman_caps` is set (used by the Pause button to suppress the action on cgroups v1 systems), `ShellWidget.binary` is set to `"podman"`, and `ComposeView.compose_cmd` is set.

**`closeEvent`** performs an ordered shutdown:
1. `shell.disconnect_shell()` — terminates the PTY subprocess and closes the master fd.
2. `_stop_resource_monitor()` — signals the monitor thread and waits up to 1500 ms.
3. Iterates `monitor_windows` and joins each floating monitor thread.
4. `monitor_windows.clear()`.
5. `event.accept()`.

---

## 7. Module: `docker_client.py`

### `_is_podman_docker_shim() -> bool`

Detects whether the `docker` binary on `PATH` is the `podman-docker` compatibility shim installed on Arch Linux and similar distributions. The shim is a shell script that delegates to Podman, and it causes a `"unsupported protocol: Yunix"` error when used with `docker compose`. Detection proceeds through three independent signals:

1. Read the first 4 bytes of the binary. ELF executables start with `\x7fELF`. A shell script starts with `#!` or similar text — so any non-ELF magic is treated as a shim.
2. Run `docker info --format '{{.ServerVersion}}'` and check if the output contains `"podman"`.
3. The first check failing (OSError) falls through to the second.

### `get_compose_command() -> list[str]`

Returns the compose command as a list suitable for `subprocess.Popen`. Tries five candidates in priority order, short-circuiting on the first successful one. `docker compose version` is validated by checking that its stdout does not contain `"podman"` — a secondary guard against the shim case where `docker compose` might succeed but actually invoke Podman.

### `DockerClient`

Wraps `docker.from_env()`. The `@handle_docker_api_error` decorator is defined as a `@staticmethod` to avoid receiving `self` as its first argument (since it is applied at class definition time before instances exist). The inner `wrapper` function does receive `self` as its first argument because it has the standard instance method signature.

`perform_container_action(container, action_func, action_name)` calls `action_func()` (e.g. `container.start`), then immediately calls `containers.get(container.id)` to return a refreshed container object. This avoids stale `status` fields in the returned object — the Docker SDK's container objects are snapshots from the time they were fetched.

---

## 8. Module: `podman_utils.py`

### Socket detection

`_candidate_sockets()` returns paths in priority order. On Linux, the XDG runtime socket (`/run/user/<uid>/podman/podman.sock`) is preferred over the rootful socket (`/run/podman/podman.sock`) because rootless Podman is the recommended setup. The `XDG_RUNTIME_DIR` environment variable is checked and prepended if set.

`detect_podman_socket()` separates candidates into `accessible` (user has `R_OK | W_OK`) and `inaccessible` (exists but permission denied). The first accessible socket is returned; if none are accessible but one exists, the inaccessible socket is returned anyway so `get_podman_client()` can produce a specific `PermissionError` message rather than a generic "not found" error.

### `PodmanCapabilities`

Populated by `detect(client)` immediately after connection:

- `pause_supported`: Podman requires cgroups v2 for pause/unpause. Detected via `client.info()['CgroupVersion']` — if this equals `"2"`, pause is supported.
- `compose_supported`: Checks for `podman-compose` or `docker-compose` on PATH via `shutil.which`.
- `swarm_supported`: Always `False` — Podman does not implement the Swarm API.

`warnings()` returns a human-readable list of limitations, logged to the UI when the Podman backend is activated.

### `get_podman_client()`

After detecting the socket and checking permissions, creates a `docker.DockerClient(base_url=sock, timeout=10)` and calls `client.ping()` to verify the daemon is responsive. Handles `PermissionError` both directly and when wrapped inside a generic `Exception` by docker-py (the SDK sometimes wraps low-level OS errors in its own exception hierarchy).

---

## 9. Module: `resource_monitor.py`

### `ResourceMonitorThread`

Polls container stats via `container.stats(stream=False)` every second. `stream=False` makes a single API call and returns immediately, rather than holding a long-lived HTTP connection.

**CPU calculation:**

```
cpu_delta    = cpu_stats.cpu_usage.total_usage   - prev_cpu
system_delta = cpu_stats.system_cpu_usage        - prev_system
cpu_percent  = (cpu_delta / system_delta) * num_cpus * 100.0
```

`total_usage` is a monotonically increasing counter of CPU nanoseconds consumed by all processes in the container. `system_cpu_usage` is a counter of total CPU nanoseconds elapsed on the host. The ratio gives the fraction of one CPU used, multiplied by the number of CPUs to give a percentage where 100% means one full CPU core. On the first sample, `prev_cpu` is None and `0.0` is emitted.

`num_cpus` is taken from `len(percpu_usage)` — the list of per-CPU usage values. If `percpu_usage` is absent (some runtimes omit it), `num_cpus` defaults to 1.

**RAM calculation:**

```python
cache     = mem_stats.get('stats', {}).get('cache', 0)
ram_bytes = mem_stats.get('usage', 0) - cache
```

`memory_stats.usage` includes the kernel page cache, which inflates the reading. Subtracting `stats.cache` gives the container's actual working set memory. This matches the behaviour of `docker stats` on the CLI.

**Disk calculation:**

`storage_stats.read_write_layer` is checked first (available on overlay2 and some other storage drivers). If absent, the function falls back to summing `value` fields from `blkio_stats.io_service_bytes_recursive` where `op == 'write'`. This gives cumulative bytes written since container start. The `or []` guard on the `io_service_bytes_recursive` fetch handles the Podman case where this key exists but its value is `None`.

**Empty stats guard:**

```python
stats = self.container.stats(stream=False)
if not stats:
    time.sleep(1)
    continue
```

Podman occasionally returns an empty response body from the stats endpoint. Without this guard, the SDK attempts JSON parsing and raises `JSONDecodeError: Expecting value: line 1 column 1`. The guard skips the iteration silently.

**Thread safety:** The thread only ever calls `self.update_graph.emit(...)` to communicate with the main thread. No shared mutable state is accessed. Signal delivery is thread-safe in Qt: signals emitted from a non-GUI thread are queued and dispatched on the main thread's event loop.

**Shutdown:** `stop()` sets `_running = False`. The thread will exit after at most one more `time.sleep(1)`. The caller **must** call `thread.wait(1500)` after `stop()`. Setting the reference to `None` before the thread exits causes `QThread::~QThread()` to call `qFatal()` → `abort()` → `SIGABRT`, which was the cause of the crash reported during development.

### `ResourceGraphWidget`

A `QWidget` embedding a `matplotlib.figure.Figure` with three `Axes` stacked vertically. Each axis maintains a 60-point `collections.deque`. On `update_graph(cpu, ram, disk)`, the new values are appended and the Y-axis limits are adjusted to `max(data) * 1.2` (with floor values of 5, 10, and 10 for CPU, RAM, and disk respectively). `canvas.draw_idle()` is used instead of `canvas.draw()` — it schedules the redraw at the next idle moment in Qt's event loop, preventing the matplotlib render from blocking input processing.

---

## 10. Module: `swarm.py`

`SwarmManager` implements all Swarm operations by invoking the Docker CLI via `subprocess.run` with `capture_output=True`, `text=True`, and `check=True`. This design was chosen over the Docker Python SDK's Swarm API because the SDK's Swarm interface is less stable and more complex than for containers and images. All privileged operations (`scale_service`, `view_nodes`, `leave_swarm`) are guarded by `is_swarm_manager()`, which runs `docker info --format '{{.Swarm.LocalNodeState}}'` and checks for `"active"` in the output.

---

## 11. Module: `logs.py`

`Logger` wraps `logging.getLogger(__name__)`. The root logger is configured with `logging.basicConfig` at module import time to write to `event_log.log` at `INFO` level.

`resource_monitor.py` configures its own named logger separately with a `FileHandler` pointing to `monitor_log.log`. This bypasses the root handler and keeps resource monitor output in a dedicated file. The `if not logger.handlers` guard prevents duplicate handlers if the module is imported multiple times.

`log_error(msg)` writes at `ERROR` level and appends the full traceback via `traceback.format_exc()`, even if no exception is currently active (in which case `format_exc()` returns `"NoneType: None"`).

---

## 12. Module: `terminal_utils.py`

Provides cross-platform terminal launching via `open_terminal_with_command(command)`. Platform dispatch:

- **Windows**: Uses `wt` (Windows Terminal) if available, otherwise `cmd /k` via `shell=True`.
- **macOS**: Uses `osascript` to send an AppleScript `do script` command to `Terminal.app`.
- **Linux**: Calls `detect_terminal()` to find the first available emulator from a priority list, then launches it with the correct flag syntax. `gnome-terminal`, `mate-terminal`, and `tilix` use `-- bash -c <command>`; `xfce4-terminal` uses `-e "bash -c '<command>'"` (note quoting); all others use `-e <command>`.

This module is **not used by `ShellWidget`**. The in-app terminal is self-contained and uses PTY directly. `terminal_utils` is available as infrastructure for future features that may need to spawn an external window (e.g. an "Open in external terminal" button).

---

## 13. Threading Model

| Thread | Class | Communicates via |
|---|---|---|
| Main (Qt event loop) | — | All Qt widgets and SDK calls |
| Container stats | `ResourceMonitorThread` | `update_graph` signal (queued connection) |
| Image pull | `PullImageThread` | `progress` signal (queued connection) |
| Compose subprocess | `ComposeThread` | `output` signal, `finished_ok` signal |
| PTY output | Not a thread — `QSocketNotifier` | `activated` signal (direct connection, same thread) |

All `QThread` instances are stopped by setting a `_running` flag and waiting for them to exit cleanly (`thread.wait(ms)`). `terminate()` is never called on running threads, to avoid leaving the Python interpreter in an inconsistent state.

The PTY output path (`ShellWidget`) does not use a background thread. Instead, `QSocketNotifier` integrates the PTY master file descriptor directly into Qt's GLib-based event loop. When the kernel signals that data is available on the fd, Qt calls `_read_output` on the main thread — this is non-blocking by design, as `os.read(fd, 4096)` will only be called when data is actually ready.

---

## 14. Signal / Slot Map

```
ResourceMonitorThread.update_graph(float, float, float)
    └──► ContainersView._update_resources         (inline progress bars)
    └──► ResourceGraphWidget.update_graph         (floating monitor window)

PullImageThread.progress(str)
    └──► ImagesView lambda                        (log panel + QProgressDialog)

ComposeThread.output(str)
    └──► ComposeView._append_output

ComposeThread.finished_ok()
    └──► ComposeView.refresh

ComposeThread.finished()
    └──► lambda: stop_btn.setEnabled(False)

ContainersView.log_message(str)   ┐
ImagesView.log_message(str)       │
VolumesView.log_message(str)      ├──► DockerGui._append_log
NetworksView.log_message(str)     │
ComposeView.log_message(str)      │
SwarmView.log_message(str)        ┘

QTimer.timeout()
    └──► DockerGui._auto_refresh   (every 5 000 ms, only if Containers tab active)

QSocketNotifier.activated(int)
    └──► ShellWidget._read_output
```

---

## 15. Known Limitations

**Terminal emulator:**
- pyte implements the vast majority of VT100/VT220/XTERM escape sequences, but obscure sequences used by some applications may render incorrectly. Applications that use mouse reporting, bracketed paste, or the alternate screen buffer (which pyte does support) should work correctly.
- Very high-volume output that scrolls more than 2000 lines in rapid succession will push older content out of `pyte.HistoryScreen.history.top`.

**Podman:**
- Docker Swarm is not supported. The Swarm tab is disabled when Podman is the active backend.
- Pause/Unpause requires cgroups v2. The application detects this at connection time and suppresses the Pause action with a warning if cgroups v1 is in use.
- The `compose ps --format json` output format differs between `podman compose` and `podman-compose` versions; the parser handles both known field-name variants.
- Image names in compose files must be fully qualified (`docker.io/library/postgres:16-alpine`).

**Resource monitor:**
- The Disk metric measures cumulative write I/O bytes since container start, not current filesystem space consumed by the writable layer.
- `memory_stats.stats.cache` is not present in all Docker API versions or all storage drivers. When absent, the cache subtraction defaults to 0 and `usage` is reported as-is.

**Thread shutdown:**
- `thread.wait(1500)` in `_stop_resource_monitor` will block the main thread for up to 1.5 seconds if the stats thread is slow to exit. This is acceptable for user-triggered actions but would be noticeable if triggered in a tight loop.

**Remaining untranslated strings:**
- `docker_client.py` line 321: one Hungarian comment in the `get_podman_client` docstring.
- `podman_utils.py` line 257: one Hungarian inline comment.
- `main.py` lines 7–8: two Hungarian comment lines.
