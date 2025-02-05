from typing import Protocol, Iterator, Optional, Union, runtime_checkable


@runtime_checkable
class Record(Protocol):
    source: str

    def get_content(self) -> Optional[str]: ...


@runtime_checkable
class RecordContainer(Protocol):
    source: str

    def get_records(self) -> Iterator[Union[Record, "RecordContainer"]]: ...


@runtime_checkable
class Plugin(Protocol):
    """Plugin protocol"""

    def create_record_if_can_handle(
        self, source: str
    ) -> Optional[Union[Record, RecordContainer]]: ...

    def collect_records(
        self, record: Record
    ) -> Iterator[Union[Record, RecordContainer]]: ...
