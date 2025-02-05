# collector_test.py
from dataclasses import dataclass
from typing import Iterator, Optional, Union, List
import pytest

from file_prompt.plugin.base import Record, RecordContainer, Plugin
from file_prompt.collector import RecordCollector


# Test implementations
@dataclass
class MockRecord:
    source: str
    content: str = ""


@dataclass
class MockContainer:
    source: str
    records: List[Union[MockRecord, "MockContainer"]]

    def get_records(self) -> Iterator[Union[Record, RecordContainer]]:
        yield from self.records


class MockPlugin:
    def __init__(
        self,
        handled_sources: List[str],
        found_records: List[Union[Record, RecordContainer]],
    ):
        self.handled_sources = handled_sources
        self.found_records = found_records
        self.collected_from: List[str] = (
            []
        )  # Track which records we tried to collect from

    def create_record_if_can_handle(
        self, source: str
    ) -> Optional[Union[Record, RecordContainer]]:
        return MockRecord(source=source) if source in self.handled_sources else None

    def collect_records(
        self, record: Record
    ) -> Iterator[Union[Record, RecordContainer]]:
        self.collected_from.append(record.source)
        yield from self.found_records


def test_simple_record_collection():
    """Test collecting from a single record"""
    plugin = MockPlugin(handled_sources=["source1"], found_records=[])
    collector = RecordCollector([plugin])

    records = list(collector.collect_records(["source1"]))

    assert len(records) == 1
    assert records[0].source == "source1"
    assert plugin.collected_from == ["source1"]


def test_multiple_plugins():
    """Test that all plugins get a chance to collect from records"""
    plugin1 = MockPlugin(
        handled_sources=["source1"], found_records=[MockRecord("found_by_plugin1")]
    )
    plugin2 = MockPlugin(
        handled_sources=["source2"], found_records=[MockRecord("found_by_plugin2")]
    )

    collector = RecordCollector([plugin1, plugin2])
    records = list(collector.collect_records(["source1"]))

    # Original record plus what plugin1 found (plugin2's records aren't included
    # since it doesn't handle source1)
    assert len(records) == 3
    assert {r.source for r in records} == {
        "source1",
        "found_by_plugin1",
        "found_by_plugin2",
    }


def test_container_handling():
    """Test handling of container records"""
    contained_record = MockRecord("contained")
    container = MockContainer("container", [contained_record])

    plugin = MockPlugin(
        handled_sources=["container"],
        found_records=[],  # No additional records found from collection
    )

    # Override create_record to return our container
    def create_record_override(source: str):
        return container if source == "container" else None

    plugin.create_record_if_can_handle = create_record_override

    collector = RecordCollector([plugin])
    records = list(collector.collect_records(["container"]))

    # Should find: container and contained record
    # (No additional records since plugin.found_records is empty)
    assert len(records) == 2
    assert {r.source for r in records} == {"container", "contained"}


def test_cycle_prevention():
    """Test that cycles in record references are handled"""
    # Create a cycle: record1 -> record2 -> record1
    record1 = MockRecord("record1")
    record2 = MockRecord("record2")

    plugin = MockPlugin(
        handled_sources=["record1"], found_records=[record2]  # record1 finds record2
    )
    plugin2 = MockPlugin(
        handled_sources=["record2"], found_records=[record1]  # record2 finds record1
    )

    collector = RecordCollector([plugin, plugin2])
    records = list(collector.collect_records(["record1"]))

    # Should only process each record once despite cycle
    assert len(records) == 2
    assert {r.source for r in records} == {"record1", "record2"}


def test_nested_containers():
    """Test handling of nested containers"""
    leaf_record = MockRecord("leaf")
    inner_container = MockContainer("inner", [leaf_record])
    outer_container = MockContainer("outer", [inner_container])

    plugin = MockPlugin(
        handled_sources=["outer"],
        found_records=[],  # No additional records found from collection
    )

    def create_record_override(source: str):
        return outer_container if source == "outer" else None

    plugin.create_record_if_can_handle = create_record_override

    collector = RecordCollector([plugin])
    records = list(collector.collect_records(["outer"]))

    # Should find: outer container, inner container, leaf record
    # (No additional records since plugin.found_records is empty)
    assert len(records) == 3
    assert {r.source for r in records} == {"outer", "inner", "leaf"}


def test_plugin_order():
    """Test that first plugin that can handle source is used"""
    plugin1 = MockPlugin(
        handled_sources=["source"], found_records=[MockRecord("found_by_plugin1")]
    )
    plugin2 = MockPlugin(
        handled_sources=["source"], found_records=[MockRecord("found_by_plugin2")]
    )

    collector = RecordCollector([plugin1, plugin2])
    records = list(collector.collect_records(["source"]))

    # Should find original record and what both plugins found
    assert len(records) == 3
    assert {r.source for r in records} == {
        "source",
        "found_by_plugin1",
        "found_by_plugin2",
    }
