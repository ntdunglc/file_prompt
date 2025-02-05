# plugin/file.py
# plugin/file.py
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Union
import re
import logging
import pathspec

from file_prompt.plugin.base import Record, RecordContainer, Plugin

logger = logging.getLogger(__name__)


@dataclass
class FileSystemConfig:
    include_patterns: List[str]
    exclude_patterns: List[str]
    instruction_extensions: List[str]
    prefix_map: Dict[str, str]
    respect_gitignore: bool
    ignore_hidden: bool


@dataclass
class FileRecord(Record):
    source: str
    path: Path  # Additional field specific to file records

    def get_content(self) -> Optional[str]:
        try:
            return self.path.read_text()
        except Exception as e:
            logger.debug(f"Error reading file {self.path}: {e}")
            return None


@dataclass
class DirectoryRecord(RecordContainer):
    source: str
    path: Path  # Additional field specific to directories
    config: FileSystemConfig

    def get_records(self) -> Iterator[Union[Record, RecordContainer]]:
        plugin = FileSystemPlugin(self.config)  # Create plugin instance here
        if plugin.is_path_ignored(self.path):  # Use plugin's _is_path_ignored method
            return
        for child in self.path.iterdir():
            if self.config.ignore_hidden and child.name.startswith("."):
                continue
            if plugin.is_path_ignored(child):
                continue
            if child.is_dir():
                yield DirectoryRecord(
                    source=str(child),
                    path=child,
                    config=self.config,
                )  # Pass plugin instance
            else:
                yield FileRecord(source=str(child), path=child)


class FileSystemPlugin(Plugin):
    def __init__(self, config: FileSystemConfig):
        self.config = config
        self.is_path_ignored = self._is_path_ignored  # Make public
        self._gitignore_cache: Dict[Path, Optional[pathspec.PathSpec]] = {}

    def _load_gitignore(self, directory: Path) -> Optional[pathspec.PathSpec]:
        if directory in self._gitignore_cache:
            return self._gitignore_cache[directory]

        gitignore_path = directory / ".gitignore"
        if gitignore_path.is_file():
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
                    self._gitignore_cache[directory] = spec
                    return spec
            except Exception as e:
                logger.warning(f"Error reading gitignore file at {gitignore_path}: {e}")
                self._gitignore_cache[directory] = None  # Cache failure
                return None
        else:
            parent = directory.parent
            if parent != directory:  # Avoid infinite loop at root
                spec = self._load_gitignore(parent)
                self._gitignore_cache[directory] = spec  # Cache result even if None
                return spec
            else:
                self._gitignore_cache[directory] = None
                return None

    def _is_path_ignored(self, path: Path) -> bool:
        if not self.config.respect_gitignore:
            return False

        gitignore_spec = self._load_gitignore(
            path.parent  # Always use parent directory to load gitignore
        )

        if gitignore_spec:
            gitignore_dir = path.parent  # Always use parent directory to load gitignore
            base_path = gitignore_dir.resolve()

            relative_path = str(path.resolve().relative_to(base_path))
            if path.is_dir():
                relative_path += "/"  # Append slash for directory matching
            return gitignore_spec.match_file(relative_path)
        return False

    def create_record_if_can_handle(
        self, source: str
    ) -> Optional[Union[Record, RecordContainer]]:
        try:
            if not source:  # Reject empty strings
                return None

            path = Path(
                source
            ).resolve()  # Resolve to handle symlinks and absolute paths
            if not path.exists():
                return None

            if self.config.ignore_hidden and path.name.startswith("."):
                return None

            if self.is_path_ignored(path):
                return None

            if path.is_dir():
                return DirectoryRecord(
                    source=source,
                    path=path,
                    config=self.config,
                )  # Pass plugin instance
            return FileRecord(source=source, path=path)
        except Exception as e:
            logger.debug(f"Error creating record for {source}: {e}")
            return None

    def collect_records(
        self, record: Record
    ) -> Iterator[Union[Record, RecordContainer]]:
        # Only process instruction files
        if (
            isinstance(record, FileRecord)
            and record.path.suffix[1:] not in self.config.instruction_extensions
        ):
            return

        content = record.get_content()
        if not content:
            return

        paths = self._extract_paths(content)
        for path in paths:
            resolved_path = self._resolve_path(path, record.path)
            if resolved_path and resolved_path.exists():
                if self.config.ignore_hidden and resolved_path.name.startswith(
                    "."
                ):  # Check hidden here
                    continue
                if self.is_path_ignored(resolved_path):  # Check gitignore here
                    continue
                result = self.create_record_if_can_handle(str(resolved_path))
                if result:
                    yield result

    def _extract_paths(self, content: str) -> Iterator[str]:
        # Build regex pattern to match:
        # 1. Paths starting with ./ or ../
        # 2. Absolute paths starting with /
        # 3. Paths starting with a prefix from prefix_map
        prefixes = "|".join(
            re.escape(prefix) for prefix in self.config.prefix_map.keys()
        )
        pattern = rf'(?:\.{{1,2}}/|/|(?:{prefixes})/)[^\s"\'<>:*?|]+'

        for match in re.finditer(pattern, content):
            path = match.group().strip()
            if path:
                yield path

    def _resolve_path(self, path_str: str, file_path: Path) -> Optional[Path]:
        try:
            # 1. Handle relative paths (./ or ../)
            if path_str.startswith("./") or path_str.startswith("../"):
                # Resolve relative to the file's location
                resolved = (file_path.parent / path_str).resolve()
                return resolved

            # 2. Handle absolute paths
            if path_str.startswith("/"):
                # Use absolute path as-is
                path = Path(path_str)
                return path.resolve()

            # 3. Handle prefix mappings
            for prefix, mapping in self.config.prefix_map.items():
                if path_str.startswith(prefix + "/"):
                    # Replace prefix with mapping and resolve relative to PWD
                    mapped_path = path_str.replace(prefix + "/", "", 1)
                    resolved = Path(mapping).resolve() / mapped_path
                    return resolved

            return None

        except Exception as e:
            logger.debug(
                f"Error resolving path {path_str} relative to {file_path}: {e}"
            )
            return None
