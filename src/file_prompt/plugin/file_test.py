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

    # Create hidden files and directories
    (src / ".hidden_file.txt").write_text("hidden file")
    (src / ".hidden_dir").mkdir()
    (src / ".hidden_dir" / "inner_hidden.txt").write_text("inner hidden file")

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
    assert len(records) == 3  # main.py, README.txt, nested/, but not hidden files/dirs
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
    instruction_path = file_system / "instruction.txt"  # fix typo here
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
    assert plugin.create_record_if_can_handle(None) is None  # fix typo here

    # Test with invalid path characters
    assert plugin.create_record_if_can_handle("\0invalid") is None

    # Test with empty string
    assert plugin.create_record_if_can_handle("") is None


def test_ignore_hidden_files_and_directories(file_system):
    """Test ignoring hidden files and directories."""
    config = FileSystemConfig(
        include_patterns=["*.py", "*.txt"],
        exclude_patterns=["test_*.py"],
        instruction_extensions=["txt"],
        prefix_map={"src": "."},
        respect_gitignore=False,
        ignore_hidden=True,  # Explicitly set to True
    )
    plugin = FileSystemPlugin(config)
    dir_path = file_system / "src"
    record = plugin.create_record_if_can_handle(str(dir_path))
    assert isinstance(record, DirectoryRecord)
    records = list(record.get_records())

    hidden_files_present = any(r.source.endswith(".hidden_file.txt") for r in records)
    hidden_dir_present = any(r.source.endswith(".hidden_dir") for r in records)

    assert not hidden_files_present, "Hidden files should be ignored"
    assert not hidden_dir_present, "Hidden directories should be ignored"


def test_show_hidden_files_and_directories(file_system):
    """Test showing hidden files and directories."""
    config = FileSystemConfig(
        include_patterns=["*.py", "*.txt"],
        exclude_patterns=["test_*.py"],
        instruction_extensions=["txt"],
        prefix_map={"src": "."},
        respect_gitignore=False,
        ignore_hidden=False,  # Explicitly set to False to show hidden
    )
    plugin = FileSystemPlugin(config)
    dir_path = file_system / "src"
    record = plugin.create_record_if_can_handle(str(dir_path))
    assert isinstance(record, DirectoryRecord)
    records = list(record.get_records())

    hidden_files_present = any(r.source.endswith(".hidden_file.txt") for r in records)
    hidden_dir_present = any(r.source.endswith(".hidden_dir") for r in records)

    assert hidden_files_present, "Hidden files should be shown"
    assert hidden_dir_present, "Hidden directories should be shown"


def test_respect_gitignore_option(file_system):
    """Test respecting .gitignore."""
    gitignore_content = """
    *.txt
    nested/
    """
    (file_system / "src" / ".gitignore").write_text(gitignore_content)

    config = FileSystemConfig(
        include_patterns=["*.py", "*.txt"],
        exclude_patterns=["test_*.py"],
        instruction_extensions=["txt"],
        prefix_map={"src": "."},
        respect_gitignore=True,  # Explicitly set to True
        ignore_hidden=True,
    )
    plugin = FileSystemPlugin(config)
    dir_path = file_system / "src"
    record = plugin.create_record_if_can_handle(str(dir_path))
    assert isinstance(
        record, DirectoryRecord
    ), f"Expected DirectoryRecord, but got {type(record)} for {dir_path}"
    records = list(record.get_records())
    print()

    txt_files_present = any(r.source.endswith(".txt") for r in records)
    nested_dir_present = any(
        isinstance(r, DirectoryRecord) and r.source.endswith("nested") for r in records
    )

    assert not txt_files_present, ".txt files should be ignored by gitignore"
    assert not nested_dir_present, "nested directory should be ignored by gitignore"
    assert any(
        r.source.endswith("main.py") for r in records
    ), "main.py should still be present"


def test_no_gitignore_option(file_system):
    """Test ignoring .gitignore."""
    gitignore_content = """
    *.txt
    nested/
    """
    (file_system / "src" / ".gitignore").write_text(gitignore_content)

    config = FileSystemConfig(
        include_patterns=["*.py", "*.txt"],
        exclude_patterns=["test_*.py"],
        instruction_extensions=["txt"],
        prefix_map={"src": "."},
        respect_gitignore=False,  # Explicitly set to False
        ignore_hidden=True,
    )
    plugin = FileSystemPlugin(config)
    dir_path = file_system / "src"
    record = plugin.create_record_if_can_handle(str(dir_path))
    assert isinstance(
        record, DirectoryRecord
    ), f"Expected DirectoryRecord, but got {type(record)} for {dir_path}"
    records = list(record.get_records())

    txt_files_present = any(r.source.endswith(".txt") for r in records)
    nested_dir_present = any(
        isinstance(r, DirectoryRecord) and r.source.endswith("nested") for r in records
    )

    assert txt_files_present, ".txt files should be present when gitignore is False"
    assert (
        nested_dir_present
    ), "nested directory should be present when gitignore is False"
    assert any(
        r.source.endswith("main.py") for r in records
    ), "main.py should still be present"
