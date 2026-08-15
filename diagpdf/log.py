"""User-facing diagnostics.

Warnings go to stderr through :func:`_warn` rather than the ``logging`` module:
they are addressed at whoever ran the command, not at an operator reading a log,
and they have to survive a legacy Windows console. Library chatter — fontTools
in particular — is routed through ``logging`` and silenced by default.
"""

from __future__ import annotations

import logging
import sys

_QUIET = False


def set_quiet(quiet: bool) -> None:
    """Suppress warnings (``--quiet``)."""
    global _QUIET
    _QUIET = quiet


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Set up log levels for the run.

    fontTools reports on the header timestamps of most of the bundled fonts::

        'modified' timestamp seems very low; regarding as unix timestamp

    That is a property of those files, nothing the user can act on, and it used
    to appear on every single run. It is silenced unless --verbose is given.
    """
    set_quiet(quiet)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s', stream=sys.stderr)
    if not verbose:
        for noisy in ('fontTools', 'fontTools.ttLib', 'fontTools.subset', 'PIL'):
            logging.getLogger(noisy).setLevel(logging.ERROR)


def _printable(text: str, stream) -> str:
    """Return *text* in a form *stream* can encode.

    The Windows console defaults to a legacy code page, so characters the
    stream cannot represent are transliterated rather than shown as mojibake
    (or raising UnicodeEncodeError and taking the whole run down).
    """
    encoding = getattr(stream, 'encoding', None) or 'utf-8'
    try:
        text.encode(encoding)
    except UnicodeEncodeError:
        return text.encode(encoding, errors='replace').decode(encoding, errors='replace')
    return text


def _say(message: str = '') -> None:
    """Print a line of asked-for output, surviving a legacy console.

    Reports go to stdout because they are the answer to the command, not a
    diagnostic; --quiet does not touch them. A language name or a saved header
    can carry characters cp1252 has no room for, which used to end the run in
    a UnicodeEncodeError from ``print`` itself.
    """
    print(_printable(message, sys.stdout))


def _warn(message: str) -> None:
    """Report a non-fatal problem to the user."""
    if _QUIET:
        return
    print(_printable(f'Warning: {message}', sys.stderr), file=sys.stderr)


_WARNED_ONCE: set[str] = set()


def _warn_once(message: str) -> None:
    """Report a non-fatal problem, but only the first time it happens.

    Used for per-diagram conditions that would otherwise repeat once per
    position in a 500-position file.
    """
    if message not in _WARNED_ONCE:
        _WARNED_ONCE.add(message)
        _warn(message)


# Silence the library chatter as soon as the package is imported, so it never
# leaks even when DiagPDF is used as a library rather than through the CLI.
for _noisy in ('fontTools', 'fontTools.ttLib', 'fontTools.subset'):
    logging.getLogger(_noisy).setLevel(logging.ERROR)
