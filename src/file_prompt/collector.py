# collector.py
from typing import List, Iterator, Union
from file_prompt.plugin.base import Record, RecordContainer, Plugin


class RecordCollector:
    """Coordinates plugins and record collection"""

    def __init__(self, plugins: List[Plugin]):
        self.plugins = plugins

    def collect_records(
        self, sources: List[str]
    ) -> Iterator[Union[Record, RecordContainer]]:
        processed = set()  # Track processed records to avoid cycles

        def process_record(
            item: Union[Record, RecordContainer]
        ) -> Iterator[Union[Record, RecordContainer]]:
            if item.source in processed:
                return
            processed.add(item.source)

            yield item

            # Process container contents if it's a container
            if isinstance(item, RecordContainer):
                for record in item.get_records():
                    yield from process_record(record)
            else:
                for plugin in self.plugins:
                    for found in plugin.collect_records(item):
                        yield from process_record(found)

        for source in sources:
            # Find plugin that can handle the source
            for plugin in self.plugins:
                record = plugin.create_record_if_can_handle(source)
                if record:
                    yield from process_record(record)
                    break  # Only use first matching plugin
