# File Prompt

A Python tool for extracting and processing file paths from various sources, inspired by code2prompt, but allow prompt to reference external sources using a plugin system. This tool can scan directories, process instruction files, and generate structured reports while respecting gitignore patterns and path mappings.

## Features

- 🔍 Recursive file path collection
- 📄 Support for instruction files that reference other files
- 🎯 Path prefix mapping for flexible source organization
- 🚫 Gitignore pattern integration
- 🌳 Tree-style visualization of file structures
- 🔌 Plugin system for extensible processing
- 💾 Memory-efficient processing of large file structures

## Installation

### Local Development Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/file-prompt.git
cd file-prompt
```

2. Install in editable mode:
```bash
pip install -e .
```

## Usage

The `file-prompt` command is now available in your environment. Here are some common usage patterns:

### Basic Usage

Process the current directory:
```bash
file-prompt .
```

Process specific paths:
```bash
file-prompt path/to/directory path/to/file.txt
```

### Advanced Options

Include specific file patterns:
```bash
file-prompt . --include "*.py" --include "*.md"
```

Exclude patterns:
```bash
file-prompt . --exclude "test_*.py" --exclude "*.pyc"
```

Configure instruction file extensions:
```bash
file-prompt . --instruction_extensions txt md
```

Set path prefix mappings:
```bash
file-prompt . --prefix_map "src=./source" --prefix_map "lib=./vendor"
```

Control gitignore and hidden file behavior:
```bash
file-prompt . --no-gitignore --show-hidden
```

### Help

View all available options:
```bash
file-prompt --help
```

## Project Structure

```
src/
└── file_prompt/
    ├── __init__.py
    ├── click_app.py      # CLI implementation
    ├── collector.py      # Core collection logic
    ├── file_utils.py     # File handling utilities
    └── plugin/           # Plugin system
        ├── __init__.py
        ├── base.py       # Plugin interfaces
        └── file.py       # File system plugin
```

## Plugin System

The tool uses a plugin-based architecture for extensibility. The base plugin interfaces are:

```python
class Record(Protocol):
    source: str
    def get_content(self) -> Optional[str]: ...

class RecordContainer(Protocol):
    source: str
    def get_records(self) -> Iterator[Union[Record, "RecordContainer"]]: ...

class Plugin(Protocol):
    def create_record_if_can_handle(
        self, source: str
    ) -> Optional[Union[Record, RecordContainer]]: ...

    def collect_records(
        self, record: Record
    ) -> Iterator[Union[Record, RecordContainer]]: ...
```

## Development

### Running Tests

Tests are in the corresponding `*_test.py` files. Run them using pytest:
```bash
pytest
```

### Adding New Plugins

1. Create a new plugin file in the `plugin` directory
2. Implement the Plugin protocol
3. Register your plugin in the CLI (click_app.py)

Example plugin structure:
```python
from file_prompt.plugin.base import Plugin, Record, RecordContainer

class MyPlugin(Plugin):
    def create_record_if_can_handle(self, source: str):
        # Implementation
        pass

    def collect_records(self, record: Record):
        # Implementation
        yield record
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.