"""Named sets of render options, shared by the command line and the window.

A book of studies is a dozen flags — layout, answers section, paper, cover,
numbering — and retyping them for every chapter invites a document that quietly
does not match the last one. A profile is those choices under a name::

    diagpdf chapter1.pgn -o c1.pdf --answers --answers-cols 2 --cover \\
            --page-size a5 --save-profile studies
    diagpdf chapter2.pgn -o c2.pdf --profile studies

Only the options that differ from the defaults are stored, so a profile file
reads as the list of choices that were made, and a default changed in a later
release still reaches the profiles that never pinned it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .log import _warn
from .options import RenderOptions

PROFILES_VERSION = 1
PROFILES_PATH = Path.home() / '.diagpdf' / 'profiles.json'

# Profile names end up in messages and as JSON keys; keep them to something a
# user can retype without quoting, and that cannot reach out of the file.
NAME_RE = re.compile(r'^[\w][\w .-]{0,63}$', re.UNICODE)
MAX_NAME_LENGTH = 64


class ProfileError(ValueError):
    """Raised when a profile name is unusable or the profile does not exist."""


def check_name(name: str) -> str:
    """Return *name* stripped, or explain why it cannot be used."""
    cleaned = str(name or '').strip()
    if not cleaned:
        raise ProfileError('a profile name cannot be empty')
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ProfileError(f'profile name is too long (max {MAX_NAME_LENGTH} characters)')
    if not NAME_RE.match(cleaned):
        raise ProfileError(
            f'"{cleaned}" is not a usable profile name - use letters, digits, '
            'spaces, dots, dashes or underscores'
        )
    return cleaned


def load_all(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return every stored profile, falling back to none on any problem."""
    path = path or PROFILES_PATH
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        _warn(f'could not read {path.name} ({exc}) - no profiles are available')
        return {}

    stored = raw.get('profiles') if isinstance(raw, dict) else None
    if not isinstance(stored, dict):
        _warn(f'{path.name} does not contain any profiles')
        return {}
    return {name: values for name, values in stored.items()
            if isinstance(name, str) and isinstance(values, dict)}


def load(name: str, path: Path | None = None) -> dict[str, Any]:
    """Return one profile's stored options, or explain that it is not there."""
    name = check_name(name)
    profiles = load_all(path)
    if name not in profiles:
        known = ', '.join(sorted(profiles)) or 'none saved yet'
        raise ProfileError(f'no profile called "{name}" (available: {known})')
    return dict(profiles[name])


def save(name: str, values: dict[str, Any], path: Path | None = None) -> str:
    """Store *values* under *name*, keeping only what differs from the defaults."""
    name = check_name(name)
    # Round-tripping through RenderOptions validates what is about to be stored,
    # so a bad value is reported now rather than on every later run.
    kept = RenderOptions.from_dict(values).changed_from_defaults()

    path = path or PROFILES_PATH
    profiles = load_all(path)
    profiles[name] = kept
    _write(profiles, path)
    return name


def delete(name: str, path: Path | None = None) -> str:
    """Remove *name*, or explain that it was not there."""
    name = check_name(name)
    path = path or PROFILES_PATH
    profiles = load_all(path)
    if name not in profiles:
        known = ', '.join(sorted(profiles)) or 'none saved yet'
        raise ProfileError(f'no profile called "{name}" (available: {known})')
    del profiles[name]
    _write(profiles, path)
    return name


def describe(values: dict[str, Any]) -> list[str]:
    """Return one 'option = value' line per choice the profile pins."""
    return [f'{name} = {value!r}' for name, value in sorted(values.items())]


def _write(profiles: dict[str, dict[str, Any]], path: Path) -> None:
    """Write the profile file, reporting rather than raising if it cannot."""
    payload = {'version': PROFILES_VERSION, 'profiles': profiles}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
                        encoding='utf-8')
    except OSError as exc:
        raise ProfileError(f'could not write {path}: {exc}') from exc
