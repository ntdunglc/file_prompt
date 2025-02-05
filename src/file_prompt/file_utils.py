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
        except IsADirectoryError:
            logger.warning(f"Skipping directory: {self.path}")
            return None  # Skip directories
        except UnicodeDecodeError as e:
            logger.debug(f"Skipping binary file: {self.path}: {e}")
            return None  # Skip binary files
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
    rel_paths = [os.path.relpath(p, base_path) for p in paths]
    rel_paths.sort()

    tree_structure = {}
    for path in rel_paths:
        parts = path.split(os.sep)
        current_level = tree_structure
        for part in parts:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]

    def render_tree(structure, indent=""):
        lines = []
        items = sorted(structure.keys())
        for index, item in enumerate(items):
            prefix = "└── " if index == len(items) - 1 else "├── "
            lines.append(indent + prefix + item)
            lines.extend(render_tree(structure[item], indent + "    "))
        return lines

    tree_lines = render_tree(tree_structure)
    return "\n".join(tree_lines) if tree_lines else "└── ."
