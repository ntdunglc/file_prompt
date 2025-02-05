"""
Tests for the PathCollector class.

This module provides comprehensive testing of path collection functionality,
including pattern matching, gitignore integration, and path extraction from files.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from path_collector import PathCollector


class TestFileStructure:
    """Helper class to create and manage test file structures."""

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def create_file(self, relative_path: str, content: str = "") -> Path:
        """Create a file with optional content."""
        path = self.base_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def create_dir(self, relative_path: str) -> Path:
        """Create a directory."""
        path = self.base_path / relative_path
        path.mkdir(parents=True, exist_ok=True)
        return path


@pytest.fixture
def test_structure(tmp_path) -> TestFileStructure:
    """Create a test file structure for all tests."""
    structure = TestFileStructure(tmp_path)

    # Create basic directory structure
    structure.create_dir("src")
    structure.create_dir("docs/api")
    structure.create_dir("vendor")

    # Create test files
    structure.create_file("src/main.py", "print('main')")
    structure.create_file("src/utils.py", "def util(): pass")
    structure.create_file("docs/readme.txt", "Sample readme")
    structure.create_file("docs/api/spec.md", "API specification")
    structure.create_file("vendor/lib.js", "console.log('lib')")

    return structure


@pytest.fixture
def gitignore(test_structure: TestFileStructure) -> Path:
    """Create a .gitignore file with test patterns."""
    content = """
# Python cache
__pycache__/
*.pyc

# Dependencies
vendor/
    """
    return test_structure.create_file(".gitignore", content)


@pytest.fixture
def collector_with_gitignore(gitignore) -> PathCollector:
    """Create a PathCollector with gitignore integration enabled."""
    return PathCollector(
        instruction_extensions=["txt", "md"],
        include_patterns=[],
        exclude_patterns=[],
        prefix_map={},
        respect_gitignore=True,
    )


@pytest.fixture
def basic_collector() -> PathCollector:
    """Create a PathCollector with basic settings."""
    return PathCollector(
        instruction_extensions=["txt"],
        include_patterns=[],
        exclude_patterns=[],
        prefix_map={"project": "."},
        respect_gitignore=False,
    )


class TestPathCollector:
    """Test suite for PathCollector class."""

    def test_init(self):
        """Test PathCollector initialization with various settings."""
        collector = PathCollector(
            instruction_extensions=["txt", "md"],
            include_patterns=["*.py"],
            exclude_patterns=["test_*.py"],
            prefix_map={"src": ".", "lib": "./vendor"},
            respect_gitignore=True,
        )

        assert collector.instruction_extensions == ["txt", "md"]
        assert collector.include_patterns == ["*.py"]
        assert collector.exclude_patterns == ["test_*.py"]
        assert all(os.path.isabs(v) for v in collector.prefix_map.values())
        assert collector.respect_gitignore is True

    def test_gitignore_integration(
        self, test_structure: TestFileStructure, collector_with_gitignore: PathCollector
    ):
        """Test that .gitignore patterns are respected."""
        # Create test files that should be ignored
        vendor_file = test_structure.create_file("vendor/test.js")
        cache_file = test_structure.create_file("__pycache__/cache.pyc")

        # Create files that should not be ignored
        src_file = test_structure.create_file("src/test.py")
        docs_file = test_structure.create_file("docs/guide.md")

        # Verify gitignore patterns are applied correctly
        assert not collector_with_gitignore._is_path_allowed(str(vendor_file))
        assert not collector_with_gitignore._is_path_allowed(str(cache_file))
        assert collector_with_gitignore._is_path_allowed(str(src_file))
        assert collector_with_gitignore._is_path_allowed(str(docs_file))

        # Test collected paths
        paths = collector_with_gitignore.collect_paths([str(test_structure.base_path)])
        assert str(vendor_file) not in paths
        assert str(cache_file) not in paths
        assert str(src_file) in paths
        assert str(docs_file) in paths

    def test_path_filtering(self, test_structure: TestFileStructure):
        """Test path filtering with include and exclude patterns."""
        collector = PathCollector(
            instruction_extensions=[],
            include_patterns=["*.py", "*.txt"],
            exclude_patterns=["test_*.py"],
            prefix_map={},
            respect_gitignore=False,
        )

        # Create various test files
        py_file = test_structure.create_file("src/module.py")
        txt_file = test_structure.create_file("doc.txt")
        test_file = test_structure.create_file("test_module.py")
        js_file = test_structure.create_file("script.js")

        # Verify pattern matching
        assert collector._is_path_allowed(str(py_file))
        assert collector._is_path_allowed(str(txt_file))
        assert not collector._is_path_allowed(str(test_file))
        assert not collector._is_path_allowed(str(js_file))

        # Test collected paths
        paths = collector.collect_paths([str(test_structure.base_path)])
        assert str(py_file) in paths
        assert str(txt_file) in paths
        assert str(test_file) not in paths
        assert str(js_file) not in paths

    def test_extract_paths_from_file(self, test_structure: TestFileStructure):
        """Test path extraction from file content."""
        # Create files that will be referenced
        file1 = test_structure.create_file("data/file1.txt")
        file2 = test_structure.create_file("data/file2.txt")
        file3 = test_structure.create_file("src/util/helper.py")

        # Create instruction file with various path formats
        instruction_content = """
        Files to process:
        ./data/file1.txt
        ./data/file2.txt
        src/util/helper.py
        /some/non/existent/path.txt
        """
        instruction_file = test_structure.create_file(
            "instructions.txt", instruction_content
        )

        collector = PathCollector(
            instruction_extensions=["txt"],
            include_patterns=[],
            exclude_patterns=[],
            prefix_map={"src": str(test_structure.base_path / "src")},
            respect_gitignore=False,
        )

        # Extract paths from instruction file
        extracted = collector._extract_paths_from_file(instruction_file, set())

        # Verify only existing files are included
        assert str(file1.resolve()) in extracted
        assert str(file2.resolve()) in extracted
        assert str(file3.resolve()) in extracted
        assert "/some/non/existent/path.txt" not in extracted

    def test_prefix_mapping(self, test_structure: TestFileStructure):
        """Test path collection with prefix mapping."""
        # Create test files with prefix-mapped paths
        root_dir = test_structure.create_dir("project")
        src_dir = test_structure.create_dir("project/src")
        test_file = test_structure.create_file("project/src/main.py")

        # Create instruction file with mapped paths
        instruction_content = """
        Project files:
        root/src/main.py
        """
        instruction_file = test_structure.create_file(
            "instructions.txt", instruction_content
        )

        collector = PathCollector(
            instruction_extensions=["txt"],
            include_patterns=[],
            exclude_patterns=[],
            prefix_map={"root": str(root_dir)},
            respect_gitignore=False,
        )

        # Collect paths and verify prefix mapping
        paths = collector.collect_paths([str(instruction_file)])
        assert str(test_file.resolve()) in paths
        assert str(instruction_file.resolve()) in paths

    def test_recursive_instruction_processing(self, test_structure: TestFileStructure):
        """Test recursive processing of instruction files."""
        # Create files that will be referenced
        file1 = test_structure.create_file("data/file1.txt")
        file2 = test_structure.create_file("data/file2.py")

        # Create nested instruction files
        instruction1_content = "Processing: ./data/file1.txt"
        instruction2_content = "Next file: ./instruction1.txt"

        instruction1 = test_structure.create_file(
            "instruction1.txt", instruction1_content
        )
        instruction2 = test_structure.create_file(
            "instruction2.txt", instruction2_content
        )

        collector = PathCollector(
            instruction_extensions=["txt"],
            include_patterns=[],
            exclude_patterns=[],
            prefix_map={},
            respect_gitignore=False,
        )

        # Verify recursive processing
        paths = collector.collect_paths([str(instruction2)])
        assert str(instruction1.resolve()) in paths
        assert str(instruction2.resolve()) in paths
        assert str(file1.resolve()) in paths

    def test_hidden_files(self, test_structure: TestFileStructure):
        """Test that hidden files and directories are properly handled."""
        # Create a hidden directory and some files within it
        hidden_dir = test_structure.create_dir(".hidden")
        hidden_file = test_structure.create_file(".hidden/file.txt")
        hidden_root_file = test_structure.create_file(".config")

        # Create a visible file for comparison
        visible_file = test_structure.create_file("visible.txt")

        # Test with hidden files ignored (default behavior)
        collector = PathCollector(
            instruction_extensions=[],
            include_patterns=[],
            exclude_patterns=[],
            prefix_map={},
            respect_gitignore=False,
            ignore_hidden=True,
        )

        paths = collector.collect_paths([str(test_structure.base_path)])

        # Verify hidden files are excluded
        assert (
            str(hidden_file.resolve()) not in paths
        ), "Hidden file in hidden directory should be excluded"
        assert (
            str(hidden_root_file.resolve()) not in paths
        ), "Hidden file in root should be excluded"
        assert str(visible_file.resolve()) in paths, "Visible file should be included"

        # Test with hidden files allowed
        collector_with_hidden = PathCollector(
            instruction_extensions=[],
            include_patterns=[],
            exclude_patterns=[],
            prefix_map={},
            respect_gitignore=False,
            ignore_hidden=False,
        )

        paths_with_hidden = collector_with_hidden.collect_paths(
            [str(test_structure.base_path)]
        )

        # Verify hidden files are included when ignore_hidden is False
        assert (
            str(hidden_file.resolve()) in paths_with_hidden
        ), "Hidden file in hidden directory should be included"
        assert (
            str(hidden_root_file.resolve()) in paths_with_hidden
        ), "Hidden file in root should be included"
        assert (
            str(visible_file.resolve()) in paths_with_hidden
        ), "Visible file should still be included"

    def test_error_handling(
        self, test_structure: TestFileStructure, basic_collector: PathCollector
    ):
        """Test error handling for various failure scenarios."""
        # Test with non-existent path
        paths = basic_collector.collect_paths(["non_existent_path"])
        assert not paths

        # Test with unreadable file
        with patch("builtins.open", side_effect=PermissionError):
            paths = basic_collector.collect_paths(["/mock/path"])
            assert not paths

        # Test with invalid path format
        with pytest.raises(Exception):
            basic_collector.collect_paths(["\0invalid"])

        # Test with corrupted gitignore
        with patch(
            "pathspec.PathSpec.from_lines", side_effect=ValueError("Invalid pattern")
        ):
            collector = PathCollector(
                instruction_extensions=[],
                include_patterns=[],
                exclude_patterns=[],
                prefix_map={},
                respect_gitignore=True,
            )
            assert collector.gitignore_spec is None


if __name__ == "__main__":
    pytest.main([__file__])
