from dataclasses import dataclass
from typing import Dict


@dataclass
class MimeType:
    type: str
    parameters: Dict[str, str]

    def __str__(self) -> str:
        return f"MimeType(type={self.type}, parameters={self.parameters})"

    @classmethod
    def from_content_type(cls, content_type: str) -> "MimeType":
        parts = content_type.split(";")
        return MimeType(parts[0], dict(part.split("=") for part in parts[1:]))
