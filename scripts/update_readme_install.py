#!/usr/bin/env python3
"""
Update the README.md to include the pipx install command for the latest tag.

This script expects one argument: the version tag (e.g., v0.1.0).
It replaces the content inside the markers in README.md:

<!-- INSTALL_LATEST_START -->
... auto-generated block ...
<!-- INSTALL_LATEST_END -->

with the latest pipx command derived from the tag.
"""
from __future__ import annotations

import pathlib
import re
import sys

MARKER_START = "<!-- INSTALL_LATEST_START -->"
MARKER_END = "<!-- INSTALL_LATEST_END -->"


def build_block(tag: str) -> str:
    version = tag.lstrip("v").strip()
    url = (
        f"https://github.com/dil-dabalogh/tmiplus/releases/download/"
        f"v{version}/tmiplus-{version}-py3-none-any.whl"
    )
    lines = [
        MARKER_START,
        "```bash",
        f"pipx install {url}",
        "```",
        MARKER_END,
        "",
    ]
    return "\n".join(lines)


def replace_block(readme_text: str, new_block: str) -> str:
    pattern = re.compile(
        rf"{re.escape(MARKER_START)}[\s\S]*?{re.escape(MARKER_END)}",
        re.MULTILINE,
    )
    if not pattern.search(readme_text):
        # Append at the end if the block doesn't exist
        if not readme_text.endswith("\n"):
            readme_text += "\n"
        return readme_text + "\n" + new_block + "\n"
    return pattern.sub(new_block, readme_text)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: update_readme_install.py vX.Y.Z", file=sys.stderr)
        return 2
    tag = sys.argv[1]

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    readme_path = repo_root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")

    new_block = build_block(tag)
    updated = replace_block(readme_text, new_block)

    if updated != readme_text:
        readme_path.write_text(updated, encoding="utf-8")
        print("README.md updated.")
    else:
        print("README.md already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
