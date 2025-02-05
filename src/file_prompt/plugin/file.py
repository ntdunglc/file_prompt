# plugin/file.py
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Union
import re

from file_prompt.plugin.base import Record, RecordContainer, Plugin


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
        except Exception:
            return None


@dataclass
class DirectoryRecord(RecordContainer):
    source: str
    path: Path  # Additional field specific to directories

    def get_records(self) -> Iterator[Union[Record, RecordContainer]]:
        for child in self.path.iterdir():
            if child.is_dir():
                yield DirectoryRecord(source=str(child), path=child)
            else:
                yield FileRecord(source=str(child), path=child)


class FileSystemPlugin(Plugin):
    def __init__(self, config: FileSystemConfig):
        self.config = config

    def create_record_if_can_handle(
        self, source: str
    ) -> Optional[Union[Record, RecordContainer]]:
        try:
            if not source:  # Reject empty strings
                return None

            path = Path(source)
            if not path.exists():
                return None

            if path.is_dir():
                return DirectoryRecord(source=source, path=path)
            return FileRecord(source=source, path=path)
        except Exception:
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
                return resolved if resolved.exists() else None

            # 2. Handle absolute paths
            if path_str.startswith("/"):
                # Use absolute path as-is
                path = Path(path_str)
                return path if path.exists() else None

            # 3. Handle prefix mappings
            for prefix, mapping in self.config.prefix_map.items():
                if path_str.startswith(prefix + "/"):
                    # Replace prefix with mapping and resolve relative to PWD
                    mapped_path = path_str.replace(prefix + "/", "", 1)
                    resolved = Path(mapping).resolve() / mapped_path
                    return resolved if resolved.exists() else None

            return None

        except Exception:
            return None
