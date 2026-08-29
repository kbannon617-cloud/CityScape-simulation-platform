"""
Minimal .env file loader using only the standard library.

Deliberately does not depend on python-dotenv or any third-party package,
to stay within the approved runtime dependency whitelist (Master Prompt,
Section 2 / Section 7). Parses simple KEY=VALUE lines; does not support
multi-line values, variable expansion, or export statements.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from path into os.environ.

    Existing environment variables are never overwritten - a real
    environment variable always wins over a value from the file.
    Silently does nothing if the file does not exist, so this is always
    safe to call speculatively (e.g. in production where .env may not
    be present and real env vars are set another way).
    """
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # Strip a single layer of matching surrounding quotes, if present.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        os.environ.setdefault(key, value)
