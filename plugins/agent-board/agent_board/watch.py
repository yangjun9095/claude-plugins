"""`abd board --watch` -- repaint on an interval without ever stalling.

Two rules shape this.

**The scan runs on a worker thread.** A cold scan measured 32 s of pure I/O wait on
a 65-worktree repo. Doing that on the main loop would freeze the display and eat
the keypress that was meant to quit.

**Repaint is clear-screen, not cursor-up-in-place.** Line counts already vary with
width (66/64/60/58/51/52 measured) and vary again between refreshes as dirty state
and job counts change, so moving the cursor up by "the number of lines I printed
last time" desynchronises the moment anything changes height.
"""
import sys
import threading
import time

CLEAR = "\x1b[H\x1b[2J"
MIN_INTERVAL = 15.0


def clamp_interval(value):
    """A 15 s floor. Faster is not more informative -- git status over lustre is
    the cost -- and it turns a monitor into a load generator on a shared node."""
    try:
        seconds = float(value) if value is not None else MIN_INTERVAL
    except (TypeError, ValueError):
        seconds = MIN_INTERVAL
    return max(MIN_INTERVAL, seconds)


class Refresher(object):
    """Runs `build()` on a worker thread; `latest()` never blocks."""

    def __init__(self, build):
        self._build = build
        self._lock = threading.Lock()
        self._data = None
        self._error = None
        self._stamp = None
        self._busy = False
        self._stop = threading.Event()

    def start(self):
        self.trigger()

    def trigger(self):
        with self._lock:
            if self._busy or self._stop.is_set():
                return False
            self._busy = True
        thread = threading.Thread(target=self._run, name="abd-refresh")
        thread.daemon = True            # never keep the process alive on exit
        thread.start()
        return True

    def _run(self):
        data, error = None, None
        try:
            data = self._build()
        except BaseException as exc:     # a failed refresh keeps the last good board
            error = repr(exc)
        with self._lock:
            if data is not None:
                self._data = data
            self._error = error
            self._stamp = time.time()
            self._busy = False

    def latest(self):
        with self._lock:
            return self._data, self._error, self._stamp, self._busy

    def stop(self):
        self._stop.set()


class KeyReader(object):
    """Non-blocking single keypresses, only when stdin is a real tty.

    Without a tty (a pipe, a CI log, `watch abd board`) there is nothing to read
    and cbreak mode would raise, so it degrades to "no keys" and the loop is
    interval-only. The terminal is always restored, including on an exception.
    """

    def __init__(self, stream=None):
        self._stream = stream or sys.stdin
        self._fd = None
        self._saved = None

    def __enter__(self):
        try:
            import termios
            import tty
            if not self._stream.isatty():
                return self
            self._fd = self._stream.fileno()
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        except BaseException:
            self._fd, self._saved = None, None
        return self

    def __exit__(self, *exc):
        if self._fd is not None and self._saved is not None:
            try:
                import termios
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
            except BaseException:
                pass
        return False

    def poll(self, timeout):
        """One character, or None. Sleeps up to `timeout` either way, so the caller
        can use this as its only clock."""
        if self._fd is None:
            time.sleep(timeout)
            return None
        import select
        try:
            ready, _w, _x = select.select([self._stream], [], [], timeout)
        except (OSError, ValueError):
            time.sleep(timeout)
            return None
        if not ready:
            return None
        try:
            return self._stream.read(1)
        except BaseException:
            return None


def run(build, paint, interval=None, out=None, keys=None, max_loops=None):
    """The watch loop.

    `build` returns a board dict; `paint(board, notes)` writes one frame. Returns
    the exit code. Ctrl-C and `q` both quit; `r` forces an immediate refresh.
    """
    out = out or sys.stdout
    interval = clamp_interval(interval)
    refresher = Refresher(build)
    refresher.start()
    last_state = None
    loops = 0

    try:
        with (keys or KeyReader()) as reader:
            while True:
                data, error, stamp, busy = refresher.latest()
                # Repaint on the BUSY flag as well as the timestamp. Keying on the
                # timestamp alone means a repaint only happens once a scan has
                # finished, by which point busy is False again -- so the
                # "refreshing..." indicator would never actually be seen.
                if data is not None and ((stamp, busy) != last_state or loops == 0):
                    notes = []
                    if busy:
                        notes.append("refreshing...")
                    if error:
                        notes.append("refresh failed (%s) - showing the last "
                                     "good board" % error)
                    notes.append("watching every %ds - q quits, r refreshes now"
                                 % int(interval))
                    out.write(CLEAR)
                    paint(data, notes)
                    out.flush()
                    last_state = (stamp, busy)
                elif data is None and loops == 0:
                    out.write(CLEAR)
                    out.write("agent-board: scanning...\n")
                    out.flush()

                loops += 1
                if max_loops is not None and loops >= max_loops:
                    return 0

                key = reader.poll(min(interval, 1.0))
                if key in ("q", "Q", "\x03", "\x04"):
                    return 0
                if key in ("r", "R"):
                    refresher.trigger()
                    continue
                if stamp is not None and time.time() - stamp >= interval:
                    refresher.trigger()
    except KeyboardInterrupt:
        return 0
    finally:
        refresher.stop()
        # Leave the cursor on a fresh line: the last frame ends mid-screen.
        try:
            out.write("\n")
            out.flush()
        except BaseException:
            pass
