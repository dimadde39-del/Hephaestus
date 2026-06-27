"""Tiny dependency-free slug helper used only by the disposable live smoke."""

import re


def slugify(value: str, separator: str = "-") -> str:
    """Turn a short label into a lowercase slug."""

    return re.sub(r"[^a-z0-9]", separator, value.lower()).strip(separator)
