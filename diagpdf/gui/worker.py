"""Running a generation without freezing the window.

Generation used to happen on the Tk main thread, with the progress callback
calling ``root.update()`` — which re-enters the event loop, so a click during a
long run could start a second generation on top of the first. The work now runs
on a worker thread and reports back through a queue that the main thread drains
from ``root.after``. Nothing touches a widget off the main thread.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..model import PositionDict
from ..output import generate_output


class Cancelled(Exception):
    """Raised inside the worker when the user asks it to stop."""


@dataclass(frozen=True)
class Progress:
    percent: int


@dataclass(frozen=True)
class Finished:
    out_path: Path
    count: int


@dataclass(frozen=True)
class Failed:
    error: BaseException


@dataclass(frozen=True)
class Stopped:
    pass


Event = Progress | Finished | Failed | Stopped


class GenerationJob:
    """A generation running on a background thread."""

    def __init__(
        self,
        positions: list[PositionDict],
        opts: dict,
        out_path: Path,
        generator: Callable[..., Any] = generate_output,
    ) -> None:
        self._positions = positions
        self._opts = opts
        self._out_path = Path(out_path)
        self._generator = generator
        self._events: queue.Queue[Event] = queue.Queue()
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, name='diagpdf-generate', daemon=True)

    # ── control ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        """Ask the job to stop at the next progress report."""
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def is_running(self) -> bool:
        return self._thread.is_alive()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    # ── events ───────────────────────────────────────────────────────────────

    def poll(self) -> list[Event]:
        """Return every event queued since the last call (never blocks)."""
        drained: list[Event] = []
        while True:
            try:
                drained.append(self._events.get_nowait())
            except queue.Empty:
                return drained

    # ── worker ───────────────────────────────────────────────────────────────

    def _on_progress(self, percent: int) -> None:
        if self._cancel.is_set():
            raise Cancelled
        self._events.put(Progress(percent))

    def _run(self) -> None:
        try:
            self._generator(self._positions, self._opts, self._out_path, progress=self._on_progress)
        except Cancelled:
            # A half-written file is worse than no file.
            self._out_path.unlink(missing_ok=True)
            self._events.put(Stopped())
        except BaseException as exc:      # noqa: BLE001 - reported to the user verbatim
            self._events.put(Failed(exc))
        else:
            if self._cancel.is_set():
                self._out_path.unlink(missing_ok=True)
                self._events.put(Stopped())
            else:
                self._events.put(Finished(self._out_path, len(self._positions)))
