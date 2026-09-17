"""Which exact version of this code produced a hand record.

Invariant I6 is "same seed + same engine commit + same bot version gives
byte-identical hand records". For that to mean anything the record has to say
which commit it came from, so this module asks git and caches the answer.

A working tree with uncommitted edits is not the commit it sits on, so the
identifier gets a `+dirty` suffix in that case rather than quietly claiming to
be the commit.
"""

from __future__ import annotations

import functools
import pathlib
import subprocess

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ("git", *args),
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


@functools.lru_cache(maxsize=1)
def commit_id() -> str:
    """The commit this code is running from, e.g. `1a2b3c4...` or `...+dirty`.

    Returns the string `unknown` when there is no git to ask, so a record is
    never silently missing the field.
    """
    head = _git("rev-parse", "HEAD")
    if not head:
        return "unknown"
    status = _git("status", "--porcelain")
    if status:
        return f"{head}+dirty"
    return head
