#!/usr/bin/env python3
"""
Command-line interface for the file prompt tool using the new collector implementation.
This module provides the CLI commands and output generation with plugin support.
"""

import os
import logging
from typing import Tuple, Dict, List

import click
from jinja2 import Template

from file_prompt.collector import RecordCollector
from file_prompt.plugin import FileSystemPlugin, FileSystemConfig, Record
from file_prompt.file_utils import FileInfo, generate_tree

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Template for generating the output report
TEMPLATE = """Project Path: {{ base_path }}

Source Tree:

```
{{ source_tree }}
```

{% for file in files %}
`{{ file.path }}`:

```{% if file.get_language() %}{{ file.get_language() }}{% endif %}
{{ file.get_content() }}
```

{% endfor %}"""


def parse_prefix_map(prefix_map: Tuple[str, ...]) -> Dict[str, str]:
    """Parse prefix map tuples into a dictionary."""
    try:
        return dict(p.split("=", 1) for p in prefix_map)
    except ValueError as e:
        logger.error("Invalid prefix map format. Use 'prefix=path'")
        raise click.BadParameter("Invalid prefix map format") from e


def create_file_info_list(records: List[str]) -> List[FileInfo]:
    """Create FileInfo objects from the collected records."""
    return [FileInfo(str(record)) for record in sorted(records)]


@click.command()
@click.argument("paths", nargs=-1, required=True)
@click.option(
    "--instruction_extensions",
    "-i",
    multiple=True,
    default=["txt"],
    help="File extensions to treat as instruction files",
)
@click.option("--include", multiple=True, help="Glob patterns to include")
@click.option("--exclude", multiple=True, help="Glob patterns to exclude")
@click.option(
    "--gitignore/--no-gitignore",
    default=True,
    help="Whether to respect .gitignore patterns",
)
@click.option(
    "--ignore-hidden/--show-hidden",
    default=True,
    help="Whether to ignore hidden files (starting with .)",
)
@click.option(
    "--prefix_map",
    multiple=True,
    default=["google3=."],
    help="Prefix mappings in format prefix=path",
)
def main(
    paths: Tuple[str, ...],
    instruction_extensions: Tuple[str, ...],
    include: Tuple[str, ...],
    exclude: Tuple[str, ...],
    gitignore: bool,
    ignore_hidden: bool,
    prefix_map: Tuple[str, ...],
) -> None:
    """Process file paths and generate a project structure report using the plugin system."""

    try:
        # Create filesystem config
        fs_config = FileSystemConfig(
            instruction_extensions=list(instruction_extensions),
            include_patterns=list(include),
            exclude_patterns=list(exclude),
            prefix_map=parse_prefix_map(prefix_map),
            respect_gitignore=gitignore,
            ignore_hidden=ignore_hidden,
        )

        # Initialize plugins
        plugins = [FileSystemPlugin(fs_config)]

        # Create collector with plugins
        collector = RecordCollector(plugins)

        # Collect all records
        collected_records = list(collector.collect_records(list(paths)))

        if not collected_records:
            logger.warning("No files found matching the specified criteria")
            return

        # Extract file paths from records
        file_paths = [
            record.source
            for record in collected_records
            if hasattr(record, "source") and isinstance(record, Record)
        ]

        # Create FileInfo objects for rendering
        files = create_file_info_list(file_paths)
        base_path = os.getcwd()

        # Render the template
        template = Template(TEMPLATE)
        try:
            output = template.render(
                base_path=base_path,
                source_tree=generate_tree(file_paths, base_path),
                files=files,
            )
            click.echo(output)
        except Exception as e:
            logger.error(f"Error generating output: {e}")
            raise click.ClickException("Failed to generate output") from e

    except Exception as e:
        logger.error(f"Error processing files: {e}")
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
