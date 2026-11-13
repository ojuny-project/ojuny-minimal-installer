"""Curses primitives for the installer.

Only the standard library is used so the live image needs nothing beyond
python3. Every screen is a list of rows; a row edits one setting.
"""

import curses
import threading
import time
import traceback


class Abort(Exception):
    pass


class Field:
    def __init__(self, key, label, kind="text", get=None, set=None, options=None,
                 help="", secret=False):
        if kind not in ("text", "secret", "choice", "bool", "info"):
            raise ValueError("unknown field kind: {}".format(kind))
        self.key = key
        self.label = label
        self.kind = kind
        self.get = get
        self.set = set
        self.options = options or []
        self.help = help
        self.secret = secret or kind == "secret"

    def read(self):
        value = self.get()
        if self.secret:
            return "*" * min(len(value), 24)
        if self.kind == "bool":
            return "yes" if value else "no"
        return str(value)

    def edit(self, app):
        value = self.get()
        if self.kind in ("choice", "bool") and value in self.options:
            app.prompt_choice(self.label, self.options, self.options.index(value))
        elif self.kind == "bool":
            self.set(not value)
        elif self.kind in ("choice", "text", "secret"):
            result = app.prompt_choice(self.label, self.options, _index(value, self.options)) \
                if self.kind == "choice" else app.prompt_text(self.label, value, self.secret)
            if result is not None:
                self.set(result)


def _index(value, options):
    try:
        return options.index(value)
    except ValueError:
        return 0


class App:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.scroll = 0
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.stdscr.keypad(True)
        self.colors = False
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            self.colors = curses.has_colors()
        except curses.error:
            self.colors = False

    def color(self, pair):
        if self.colors:
            return curses.color_pair(pair)
        return 0

    def size(self):
        height, width = self.stdscr.getmaxyx()
        return height, width

    def put(self, row, column, text, attr=0):
        height, width = self.size()
        if row < 0 or row >= height or column >= width:
            return
        maximum = width - column - 1
        if maximum <= 0:
            return
        try:
            self.stdscr.addnstr(row, column, text, maximum, attr)
        except curses.error:
            pass

    def frame(self, title, subtitle=None):
        height, width = self.size()
        self.stdscr.erase()
        self.put(0, 0, " Ojuny installer ", curses.A_REVERSE | curses.A_BOLD)
        self.put(0, max(0, width - 16), " minimal 0.1.0 ", curses.A_REVERSE)
        self.put(2, 2, title, curses.A_BOLD | self.color(1))
        if subtitle:
            self.put(3, 2, subtitle, curses.A_DIM)
        return height, width

    def footer(self, text):
        height, _ = self.size()
        self.put(height - 1, 0, text, curses.A_REVERSE)

    def run_screen(self, title, fields, subtitle=None, error=None, footer=None):
        """Draw a screen and return 'next', 'back' or 'quit'."""
        selected = 0
        message = error
        while True:
            height, width = self.frame(title, subtitle)
            first_row = 5
            visible = max(1, height - first_row - 3)
            if selected < self.scroll:
                self.scroll = selected
            elif selected >= self.scroll + visible:
                self.scroll = selected - visible + 1

            for offset, index in enumerate(range(self.scroll, min(len(fields), self.scroll + visible))):
                field = fields[index]
                row = first_row + offset
                marker = ">" if index == selected else " "
                attr = curses.A_BOLD if index == selected else 0
                label_width = min(26, max(12, width // 3))
                label = field.label[:label_width].ljust(label_width)
                self.put(row, 2, marker, attr)
                self.put(row, 3, label, attr)
                self.put(row, 3 + label_width + 1, field.read())

            current = fields[selected]
            help_row = height - 3
            if current.help:
                self.put(help_row, 2, current.help[: width - 4], curses.A_DIM)
            if message:
                self.put(help_row, 2, message[: width - 4], self.color(2) | curses.A_BOLD)
            self.footer(footer or "enter edit   arrows move   n next   p back   q quit")
            self.stdscr.refresh()

            key = self.stdscr.getch()
            message = None
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(fields)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(fields)
            elif key in (curses.KEY_LEFT, ord("h"), curses.KEY_RIGHT, ord("l")):
                if current.kind in ("choice", "bool"):
                    self.adjust(current, -1 if key in (curses.KEY_LEFT, ord("h")) else 1)
            elif key in (curses.KEY_ENTER, 10, 13):
                if current.kind == "info":
                    return "next"
                current.edit(self)
            elif key in (ord("n"), 9):
                return "next"
            elif key in (ord("p"), curses.KEY_BACKSPACE, 127):
                return "back"
            elif key in (ord("q"), 3):
                return "quit"

    def adjust(self, field, direction):
        value = field.get()
        if field.kind == "bool":
            field.set(not value)
            return
        index = _index(value, field.options) + direction
        field.set(field.options[index % len(field.options)])

    def prompt_text(self, label, initial, secret=False):
        """Edit one line. Returns the new text, or None when cancelled."""
        buffer = list(initial)
        cursor = len(buffer)
        while True:
            height, width = self.size()
            self.stdscr.move(height - 1, 0)
            self.stdscr.clrtoeol()
            shown = "*" * len(buffer) if secret else "".join(buffer)
            prompt = " {}: ".format(label)
            self.put(height - 1, 0, prompt, curses.A_REVERSE)
            start = len(prompt)
            room = max(1, width - start - 1)
            view = shown[-room:] if len(shown) > room else shown
            self.put(height - 1, start, view, curses.A_REVERSE)
            self.footer("enter accept   esc cancel   ctrl-u clear")
            try:
                self.stdscr.move(height - 1, min(width - 2, start + len(view)))
            except curses.error:
                pass
            self.stdscr.refresh()

            key = self.stdscr.get_wch()
            if key in ("\n", "\r", curses.KEY_ENTER):
                return "".join(buffer)
            if key == "\x1b":
                return None
            if key in ("\x7f", "\b", curses.KEY_BACKSPACE):
                if cursor > 0:
                    del buffer[cursor - 1]
                    cursor -= 1
                continue
            if key in ("\x15",):
                buffer = []
                cursor = 0
                continue
            if key == curses.KEY_LEFT:
                cursor = max(0, cursor - 1)
                continue
            if key == curses.KEY_RIGHT:
                cursor = min(len(buffer), cursor + 1)
                continue
            if key == curses.KEY_HOME:
                cursor = 0
                continue
            if key == curses.KEY_END:
                cursor = len(buffer)
                continue
            if isinstance(key, str) and key.isprintable():
                buffer.insert(cursor, key)
                cursor += 1

    def prompt_choice(self, label, options, index):
        """Pick one option. Returns the value, or None when cancelled."""
        index = max(0, min(index, len(options) - 1))
        while True:
            height, width = self.size()
            self.stdscr.erase()
            self.put(2, 2, label, curses.A_BOLD | self.color(1))
            visible = max(1, height - 8)
            start = max(0, min(index - visible // 2, len(options) - visible))
            for offset, option_index in enumerate(range(start, min(len(options), start + visible))):
                row = 5 + offset
                marker = ">" if option_index == index else " "
                attr = curses.A_BOLD if option_index == index else 0
                self.put(row, 3, marker, attr)
                self.put(row, 5, str(options[option_index]), attr)
            self.footer("enter accept   esc cancel   arrows move")
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                index = (index - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord("j")):
                index = (index + 1) % len(options)
            elif key in (curses.KEY_ENTER, 10, 13):
                return options[index]
            elif key in (ord("q"), 27):
                return None

    def message(self, title, body, footer="press enter to continue"):
        height, width = self.size()
        self.stdscr.erase()
        self.put(2, 2, title, curses.A_BOLD | self.color(1))
        row = 4
        for line in body.splitlines():
            for piece in _wrap(line, width - 6):
                self.put(row, 3, piece)
                row += 1
                if row >= height - 3:
                    break
        self.footer(footer)
        self.stdscr.refresh()
        self.stdscr.getch()


def _wrap(text, width):
    if width <= 1:
        return [text]
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


class Reporter:
    """Collects progress from the engine thread."""

    def __init__(self):
        self.lock = threading.Lock()
        self.phase = "starting"
        self.lines = []
        self.done = 0
        self.total = 0

    def set_phase(self, text):
        with self.lock:
            self.phase = text
            self.lines.append("## " + text)
        self.trim()

    def log(self, text):
        with self.lock:
            self.lines.append(text)

    def advance(self, done, total):
        with self.lock:
            self.done = done
            self.total = total

    def trim(self):
        with self.lock:
            if len(self.lines) > 2000:
                del self.lines[:-2000]

    def snapshot(self):
        with self.lock:
            return self.phase, list(self.lines), self.done, self.total


def run_progress(app, title, worker, reporter):
    """Run worker(reporter) in a thread and draw its progress.

    Returns (status, error) where status is 'done' or 'failed'.
    """
    result = {"error": None}

    def target():
        try:
            worker(reporter)
        except BaseException as error:  # the engine must not kill the UI
            result["error"] = error
            reporter.log("ERROR: {}".format(error))
            reporter.log(traceback.format_exc())

    thread = threading.Thread(target=target, daemon=True)
    thread.start()

    spinner = "|/-\\"
    tick = 0
    app.stdscr.timeout(250)
    try:
        while thread.is_alive():
            height, width = app.size()
            phase, lines, done, total = reporter.snapshot()
            app.stdscr.erase()
            app.put(0, 0, " Ojuny installer ", curses.A_REVERSE | curses.A_BOLD)
            app.put(2, 2, title, curses.A_BOLD | app.color(1))
            app.put(4, 2, "{} {}".format(spinner[tick % len(spinner)], phase))
            tick += 1

            bar_width = max(10, width - 24)
            if total > 0:
                fraction = min(1.0, done / float(total))
            else:
                fraction = 0.0
            filled = int(bar_width * fraction)
            bar = "[" + "#" * filled + "." * (bar_width - filled) + "]"
            counter = (
                "{}/{}".format(done, total)
                if total
                else ("{} paths".format(done) if done else "working")
            )
            app.put(6, 2, bar)
            app.put(6, 6 + bar_width, " " + counter)

            visible = max(1, height - 11)
            for offset, line in enumerate(lines[-visible:]):
                app.put(8 + offset, 2, line[: width - 4])
            app.footer("install in progress   do not power off")
            app.stdscr.refresh()
            time.sleep(0.25)
    finally:
        app.stdscr.timeout(-1)

    thread.join()
    if result["error"] is not None:
        return "failed", result["error"]
    return "done", None
