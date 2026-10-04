"""Optional structured extraction boundary. No provider is enabled by default."""
from typing import Protocol
class StructuredExtractor(Protocol):
    async def extract(self, *, text: str, school_name: str, source_url: str) -> dict: ...

class DisabledExtractor:
    async def extract(self, **kwargs):
        raise RuntimeError('AI extraction is disabled. Configure an authenticated provider explicitly.')
