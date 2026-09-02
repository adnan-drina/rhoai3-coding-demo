#!/usr/bin/env python3
"""OS-account home (getent/pwd), not Path.home() or $HOME.

Architect E-20260825T112249ZA: Path.home() in a KEEP gate is the defect
signature under a Hermes profile worker. Same contract as
mta-analyze-legacy.sh human_home().
"""
from __future__ import annotations

import os
import pwd
from pathlib import Path

_DEST_USER_FALLBACK = Path("/home/user")


def human_home() -> Path:
    """Return the OS-account home directory for this uid.

    Does not consult $HOME or Path.home(). Dest profile workers have a
    Hermes HOME under the profile tree; dest-init and spec-kit still
    mean the dest-user account (/home/user).
    """
    try:
        home = pwd.getpwuid(os.getuid()).pw_dir
    except KeyError:
        home = ""
    if home and os.path.isdir(home):
        return Path(home)
    return _DEST_USER_FALLBACK
