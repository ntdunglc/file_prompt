# plugin/file_test.py
import os
from pathlib import Path
import pytest
from typing import Iterator

from file_prompt.plugin.file import (
    FileSystemPlugin,
    FileSystemConfig,
    FileRecord,
    DirectoryRecord,
)


@pytest.fixture
def test_config():
    return FileSystemConfig(
        include_patterns=["*.py", "*.txt"],
        exclude_patterns=["test_*.py"],
        instruction_extensions=["txt"],
        prefix_map={"src": "."},
        respect_gitignore=True,
        ignore_hidden=True,
    )


@pytest.fixture
def file_system(tmp_path) -> Path:
    """Create a test file system structure"""
    # Create directories
    src = tmp_path / "src"
    src.mkdir()
    (src / "nested").mkdir()

    # Create files with content
    (src / "main.py").write_text("print('hello')")
    (src / "README.txt").write_text(
        """
        File references:
        ./main.py
        src/nested/util.py
        /absolute/path/file.txt
        ../outside.txt
    """
    )
    (src / "nested" / "util.py").write_text("def util(): pass")
    (src / "nested" / "data.txt").write_text("some data")

    return tmp_path


def test_create_record_file(test_config, file_system):
    """Test creating record from a file source"""
    plugin = FileSystemPlugin(test_config)

    file_path = file_system / "src" / "main.py"
    record = plugin.create_record_if_can_handle(str(file_path))

    assert isinstance(record, FileRecord)
    assert record.source == str(file_path)
    assert record.path == file_path
    assert record.get_content() == "print('hello')"


def test_create_record_directory(test_config, file_system):
    """Test creating record from a directory source"""
    plugin = FileSystemPlugin(test_config)

    dir_path = file_system / "src"
    record = plugin.create_record_if_can_handle(str(dir_path))

    assert isinstance(record, DirectoryRecord)
    assert record.source == str(dir_path)
    assert record.path == dir_path

    # Test directory contents
    records = list(record.get_records())
    assert len(records) == 3  # main.py, README.txt, nested/
    assert any(r.source.endswith("main.py") for r in records)
    assert any(r.source.endswith("README.txt") for r in records)
    assert any(isinstance(r, DirectoryRecord) for r in records)


def test_create_record_nonexistent(test_config):
    """Test handling of nonexistent paths"""
    plugin = FileSystemPlugin(test_config)
    record = plugin.create_record_if_can_handle("/nonexistent/path")
    assert record is None


def test_collect_records_from_instruction_file(test_config, file_system):
    """Test collecting records from instruction file content"""
    plugin = FileSystemPlugin(test_config)

    # Get record for README.txt
    readme_path = file_system / "src" / "README.txt"
    readme_record = plugin.create_record_if_can_handle(str(readme_path))
    assert isinstance(readme_record, FileRecord)

    # Collect referenced records
    records = list(plugin.collect_records(readme_record))

    # Should find main.py
    assert len(records) == 1
    sources = {r.source for r in records}
    assert str(file_system / "src" / "main.py") in sources


def test_collect_records_non_instruction_file(test_config, file_system):
    """Test that non-instruction files are not processed"""
    plugin = FileSystemPlugin(test_config)

    # Get record for main.py
    main_path = file_system / "src" / "main.py"
    main_record = plugin.create_record_if_can_handle(str(main_path))
    assert isinstance(main_record, FileRecord)

    # Should not collect any records from non-instruction file
    records = list(plugin.collect_records(main_record))
    assert len(records) == 0


def test_collect_records_with_prefix_map(test_config, file_system):
    """Test path resolution with prefix mapping"""
    # Update config with prefix mapping
    config = FileSystemConfig(
        **{**test_config.__dict__, "prefix_map": {"project": str(file_system / "src")}}
    )
    plugin = FileSystemPlugin(config)

    # Create instruction file with prefixed path
    instruction_path = file_system / "instruction.txt"
    instruction_path.write_text("project/nested/util.py")

    # Process instruction file
    record = plugin.create_record_if_can_handle(str(instruction_path))
    records = list(plugin.collect_records(record))

    assert len(records) == 1
    assert records[0].source == str(file_system / "src" / "nested" / "util.py")


def test_collect_records_relative_paths(test_config, file_system):
    """Test resolution of relative paths"""
    plugin = FileSystemPlugin(test_config)

    # Create nested instruction file
    nested_instruction = file_system / "src" / "nested" / "instruction.txt"
    nested_instruction.write_text(
        """
        ../main.py
        ./util.py
    """
    )

    record = plugin.create_record_if_can_handle(str(nested_instruction))
    records = list(plugin.collect_records(record))

    assert len(records) == 2
    sources = {r.source for r in records}
    assert str(file_system / "src" / "main.py") in sources
    assert str(file_system / "src" / "nested" / "util.py") in sources


def test_directory_record_iteration(test_config, file_system):
    """Test recursive directory traversal"""
    dir_path = file_system / "src"
    plugin = FileSystemPlugin(test_config)

    record = plugin.create_record_if_can_handle(str(dir_path))
    assert isinstance(record, DirectoryRecord)

    def collect_all_records(container: DirectoryRecord) -> Iterator[str]:
        for record in container.get_records():
            if isinstance(record, DirectoryRecord):
                yield record.source
                yield from collect_all_records(record)
            else:
                yield record.source

    all_sources = set(collect_all_records(record))
    expected_files = {
        str(dir_path / "main.py"),
        str(dir_path / "README.txt"),
        str(dir_path / "nested"),
        str(dir_path / "nested" / "util.py"),
        str(dir_path / "nested" / "data.txt"),
    }
    assert all_sources == expected_files


def test_create_record_with_invalid_path(test_config):
    """Test handling of invalid paths"""
    plugin = FileSystemPlugin(test_config)

    # Test with None
    assert plugin.create_record_if_can_handle(None) is None

    # Test with invalid path characters
    assert plugin.create_record_if_can_handle("\0invalid") is None

    # Test with empty string
    assert plugin.create_record_if_can_handle("") is None
