"""
Core functionality for collecting and processing file paths with support for
gitignore patterns, path mapping, and hidden file filtering.

This module provides a robust implementation for collecting and processing file paths
with features including:
- Gitignore pattern support
- Path prefix mapping
- Hidden file filtering
- Recursive path resolution
- Memory-efficient processing
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
import fnmatch

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PathCollector:
    def __init__(
        self,
        instruction_extensions: List[str],
        include_patterns: List[str],
        exclude_patterns: List[str],
        prefix_map: Dict[str, str],
        respect_gitignore: bool,
        ignore_hidden: bool = True,
    ):
        """
        Initialize the PathCollector with filtering criteria and configuration.

        Args:
            instruction_extensions: List of file extensions to treat as instruction files
            include_patterns: List of glob patterns for files to include
            exclude_patterns: List of glob patterns for files to exclude
            prefix_map: Dictionary mapping path prefixes to local paths
            respect_gitignore: Whether to respect .gitignore patterns
            ignore_hidden: Whether to ignore hidden files and directories
        """
        self.instruction_extensions = instruction_extensions
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.prefix_map = {k: os.path.abspath(v) for k, v in prefix_map.items()}
        self.respect_gitignore = respect_gitignore
        self.ignore_hidden = ignore_hidden
        self.gitignore_spec = None
        self._gitignore_dir = None
        # Store the root path for relative path resolution
        self._root_path = None

    def _is_hidden(self, path: Path) -> bool:
        """
        Check if a path is considered hidden (starts with a dot).
        Also checks parent directories to catch files in hidden directories.

        Args:
            path: Path object to check

        Returns:
            bool: True if the path or any of its parents is hidden
        """
        current = path
        while current.name:
            if current.name.startswith("."):
                return True
            current = current.parent
        return False

    def _ensure_gitignore_loaded(self, path: Path) -> None:
        """
        Ensure gitignore patterns are loaded, searching from the given path upward.
        Loads the first .gitignore file found when traversing up the directory tree.

        Args:
            path: Starting path to search from
        """
        if not self.respect_gitignore or self.gitignore_spec is not None:
            return

        current = path if path.is_dir() else path.parent
        while current.parent != current:
            gitignore_path = current / ".gitignore"
            if gitignore_path.exists():
                try:
                    with open(gitignore_path) as f:
                        patterns = [
                            line.strip()
                            for line in f.readlines()
                            if line.strip() and not line.startswith("#")
                        ]
                    self.gitignore_spec = PathSpec.from_lines(
                        GitWildMatchPattern, patterns
                    )
                    self._gitignore_dir = current
                    break
                except Exception as e:
                    logger.error(f"Error loading .gitignore at {gitignore_path}: {e}")
            current = current.parent

    def _is_path_allowed(self, path: str) -> bool:
        """
        Check if a path should be included based on filtering criteria.

        Applies multiple filters in order:
        1. Hidden file filter (if enabled)
        2. Gitignore patterns (if enabled)
        3. Explicit exclude patterns
        4. Explicit include patterns

        Args:
            path: Path string to check

        Returns:
            bool: True if the path passes all filtering criteria
        """
        try:
            path_obj = Path(path)

            # Check for hidden files/directories if ignore_hidden is enabled
            if self.ignore_hidden and self._is_hidden(path_obj):
                return False

            # Load gitignore patterns if needed
            self._ensure_gitignore_loaded(path_obj)

            # Check gitignore patterns
            if self.respect_gitignore and self.gitignore_spec and self._gitignore_dir:
                try:
                    rel_path = path_obj.relative_to(self._gitignore_dir)
                    rel_path_str = str(rel_path).replace(os.sep, "/")
                    if self.gitignore_spec.match_file(rel_path_str):
                        return False
                except ValueError:
                    pass

            # Check exclude patterns
            for pattern in self.exclude_patterns:
                if fnmatch.fnmatch(path_obj.name, pattern):
                    return False

            # Check include patterns
            if self.include_patterns:
                return any(
                    fnmatch.fnmatch(path_obj.name, p) for p in self.include_patterns
                )

            return True
        except Exception as e:
            logger.error(f"Error checking path allowance for {path}: {e}")
            return False

    def _find_root_path(self, path: Path) -> Path:
        """
        Find the root path for relative path resolution.
        This is typically the topmost directory containing our files.

        Args:
            path: Starting path to search from

        Returns:
            Path: The determined root path
        """
        if self._root_path is None:
            # Start from the given path
            current = path if path.is_dir() else path.parent
            parent = current.parent

            # Walk up until we find the topmost directory that exists
            while parent != current and parent.exists():
                current = parent
                parent = current.parent

            self._root_path = current

        return self._root_path

    def _resolve_path(
        self, path_str: str, relative_to: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Resolve a path string to an absolute Path object.

        This method handles path resolution in this order:
        1. Prefix mappings (e.g., 'src/file.txt' with src=./source)
        2. Absolute paths
        3. Explicit relative paths (./ or ../) relative to the reference file
        4. Regular paths relative to root

        Args:
            path_str: Path string to resolve
            relative_to: Optional reference path for relative path resolution

        Returns:
            Optional[Path]: Resolved path if successful, None otherwise
        """
        try:
            if not path_str or "\0" in path_str:
                return None

            # Find the root path if we haven't yet
            root_path = self._find_root_path(relative_to if relative_to else Path.cwd())

            # First check prefix mappings
            for prefix, mapping in self.prefix_map.items():
                if path_str.startswith(prefix + "/"):
                    mapped_path = Path(path_str.replace(prefix, mapping, 1))
                    resolved = mapped_path.resolve()
                    return resolved if resolved.exists() else None

            # Handle absolute paths
            if path_str.startswith("/"):
                path = Path(path_str).resolve()
                return path if path.exists() else None

            # Handle relative paths
            if relative_to:
                # For paths starting with ./ or ../
                if path_str.startswith("./") or path_str.startswith("../"):
                    # First try relative to the file's directory
                    candidate = (relative_to.parent / path_str).resolve()
                    if candidate.exists():
                        return candidate

                    # If that fails, try relative to root
                    candidate = (root_path / path_str.lstrip("./")).resolve()
                    if candidate.exists():
                        return candidate
                else:
                    # For other paths, try relative to file first
                    candidate = (relative_to.parent / path_str).resolve()
                    if candidate.exists():
                        return candidate

            # Last resort: try relative to root path
            candidate = (root_path / path_str).resolve()
            return candidate if candidate.exists() else None

        except Exception as e:
            logger.error(f"Error resolving path {path_str}: {e}")
            return None

    def _extract_paths_from_file(self, file_path: Path, visited: Set[str]) -> Set[str]:
        """
        Extract and resolve file paths from a file's content.

        Recursively processes instruction files to find additional paths.
        Uses a visited set to prevent infinite recursion.

        Args:
            file_path: Path to the file to process
            visited: Set of already visited file paths

        Returns:
            Set[str]: Set of resolved file paths found in the file
        """
        if str(file_path.absolute()) in visited:
            return set()

        visited.add(str(file_path.absolute()))
        extracted_paths = set()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Find potential paths using a comprehensive regex pattern
            potential_paths = re.finditer(
                r'(?:\.{1,2}/|/|\w+(?=/))[^\s"\'<>:*?|]+', content
            )

            for match in potential_paths:
                path_str = match.group().strip()
                if not path_str:
                    continue

                resolved_path = self._resolve_path(path_str, file_path)
                if resolved_path:
                    resolved_str = str(resolved_path)
                    if self._is_path_allowed(resolved_str):
                        extracted_paths.add(resolved_str)

                        # Recursively process instruction files
                        if resolved_path.suffix[1:] in self.instruction_extensions:
                            extracted_paths.update(
                                self._extract_paths_from_file(resolved_path, visited)
                            )

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

        return extracted_paths

    def collect_paths(self, input_paths: List[str]) -> Set[str]:
        """
        Process input paths and collect all referenced paths.

        This is the main entry point for path collection. It handles both
        directory and file inputs, processes instruction files, and applies
        all configured filters.

        Args:
            input_paths: List of input path strings to process

        Returns:
            Set[str]: Set of all collected and filtered file paths

        Raises:
            ValueError: If any input path contains null bytes
        """
        if any("\0" in path for path in input_paths):
            raise ValueError("Invalid path containing null byte")

        all_paths = set()
        visited = set()

        for path_str in input_paths:
            try:
                path = Path(path_str).resolve()

                if not path.exists():
                    logger.warning(f"Path does not exist: {path}")
                    continue

                root_path = self._find_root_path(path)

                if path.is_dir():
                    # Process directories recursively
                    for root, _, files in os.walk(path):
                        for file in files:
                            file_path = Path(root) / file
                            if self._is_path_allowed(str(file_path)):
                                all_paths.add(str(file_path))

                                # Process instruction files
                                if file_path.suffix[1:] in self.instruction_extensions:
                                    all_paths.update(
                                        self._extract_paths_from_file(
                                            file_path, visited
                                        )
                                    )

                elif path.is_file():
                    # Process individual files
                    if self._is_path_allowed(str(path)):
                        all_paths.add(str(path))

                        # Process instruction files
                        if path.suffix[1:] in self.instruction_extensions:
                            all_paths.update(
                                self._extract_paths_from_file(path, visited)
                            )

            except Exception as e:
                logger.error(f"Error processing path {path_str}: {e}")

        return all_paths
