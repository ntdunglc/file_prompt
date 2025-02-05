"""
Utilities for handling files and generating file information.
This module provides file-related helper functions and classes.
"""

import os
from pathlib import Path
from typing import Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about a file, with content loaded on demand."""

    path: str

    def get_content(self) -> Optional[str]:
        """
        Load and return the file's content.
        Content is loaded on demand to save memory.

        Returns:
            str: The file content, or None if reading fails
        """
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {self.path}: {e}")
            return None

    def get_language(self) -> str:
        """
        Determine the language for syntax highlighting based on file extension.

        Returns:
            str: The language identifier for syntax highlighting
        """
        ext = Path(self.path).suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".json": "json",
            ".svg": "svg",
            ".html": "html",
            ".css": "css",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".sh": "bash",
            ".bash": "bash",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".ts": "typescript",
        }
        return language_map.get(ext, "")


def generate_tree(paths: list[str], base_path: str) -> str:
    """
    Generate a tree-like structure visualization of the files.

    Args:
        paths: List of file paths to include in the tree
        base_path: Base path to make other paths relative to

    Returns:
        str: A formatted string representing the file tree
    """
    tree = []
    rel_paths = [os.path.relpath(p, base_path) for p in paths]
    rel_paths.sort()

    for i, path in enumerate(rel_paths):
        parts = path.split(os.sep)
        indent = "    " * (len(parts) - 1)

        # Check if this is the last item at this level
        next_parts = rel_paths[i + 1].split(os.sep) if i < len(rel_paths) - 1 else []
        is_last_at_level = (
            len(next_parts) <= len(parts)
            or next_parts[: len(parts)] != parts[: len(parts)]
        )

        prefix = "└── " if is_last_at_level else "├── "
        tree.append(f"{indent}{prefix}{parts[-1]}")

    return "\n".join(tree)
