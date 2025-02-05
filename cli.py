#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "click>=8.1.0",
#     "jinja2>=3.0.0",
#     "pathspec>=0.11.0",
# ]
# license = "MIT"
# authors = [
#     { name = "Path Extractor", email = "example@example.com" }
# ]
# description = "A memory-efficient script to extract and process file paths from various sources"
# ///

"""
Command-line interface for the path extraction tool.
This module provides the CLI commands and output generation.
"""

import os
import sys
import logging
from typing import Tuple

import click
from jinja2 import Template

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from path_collector import PathCollector
from file_utils import FileInfo, generate_tree

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

@click.command()
@click.argument('paths', nargs=-1, required=True)
@click.option('--instruction_extensions', '-i', multiple=True, default=['txt'],
              help='File extensions to treat as instruction files')
@click.option('--include', multiple=True, help='Glob patterns to include')
@click.option('--exclude', multiple=True, help='Glob patterns to exclude')
@click.option('--gitignore/--no-gitignore', default=True,
              help='Whether to respect .gitignore patterns')
@click.option('--ignore-hidden/--show-hidden', default=True,
              help='Whether to ignore hidden files (starting with .)')
@click.option('--prefix_map', multiple=True, default=['google3=.'],
              help='Prefix mappings in format prefix=path')
def main(paths: Tuple[str, ...], instruction_extensions: Tuple[str, ...],
         include: Tuple[str, ...], exclude: Tuple[str, ...],
         gitignore: bool, ignore_hidden: bool, prefix_map: Tuple[str, ...]):
    """Process file paths and generate a project structure report."""
    
    # Convert prefix_map tuples to dictionary
    try:
        prefix_dict = dict(p.split('=', 1) for p in prefix_map)
    except ValueError as e:
        logger.error("Invalid prefix map format. Use 'prefix=path'")
        raise click.BadParameter("Invalid prefix map format") from e
    
    # Initialize path collector with the new ignore_hidden parameter
    collector = PathCollector(
        instruction_extensions=list(instruction_extensions),
        include_patterns=list(include),
        exclude_patterns=list(exclude),
        prefix_map=prefix_dict,
        respect_gitignore=gitignore,
        ignore_hidden=ignore_hidden
    )
    
    # Collect all paths
    all_paths = collector.collect_paths(list(paths))
    if not all_paths:
        logger.warning("No files found matching the specified criteria")
        return
    
    # Create FileInfo objects for rendering
    files = [FileInfo(path) for path in sorted(all_paths)]
    base_path = os.getcwd()
    
    # Render the template
    template = Template(TEMPLATE)
    try:
        output = template.render(
            base_path=base_path,
            source_tree=generate_tree(list(all_paths), base_path),
            files=files
        )
        click.echo(output)
    except Exception as e:
        logger.error(f"Error generating output: {e}")
        raise click.ClickException("Failed to generate output") from e

if __name__ == '__main__':
    main()