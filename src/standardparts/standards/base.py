"""Common interface every standard part generator implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from build123d import Part


class ParameterError(ValueError):
    """Raised when a request asks for a part the standard does not define."""


@dataclass(frozen=True)
class Option:
    value: str
    label: str


@dataclass(frozen=True)
class Parameter:
    """One user-selectable input, described so the web UI can render it.

    kind "select" offers fixed `options`. kind "length" is a number with
    preferred values that depend on another parameter: `preferred` maps that
    parameter's value to the list of standard lengths, and `limits` maps it
    to the allowed [min, max] when a custom value is entered.
    """

    name: str
    label: str
    kind: str
    default: str | float
    options: list[Option] = field(default_factory=list)
    depends_on: str | None = None
    preferred: dict[str, list[float]] = field(default_factory=dict)
    limits: dict[str, list[float]] = field(default_factory=dict)
    unit: str | None = None
    help: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, [], {})}


@dataclass
class Dimension:
    symbol: str
    label: str
    value: float | str | None
    unit: str = "mm"


class Standard(ABC):
    id: str
    title: str
    summary: str
    category: str
    source: str

    @abstractmethod
    def parameters(self) -> list[Parameter]: ...

    @abstractmethod
    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Turn raw query values into checked, typed parameters."""

    @abstractmethod
    def designation(self, params: dict[str, Any]) -> str:
        """Human designation, e.g. 'ISO 4762 - M6 x 20'."""

    @abstractmethod
    def file_stem(self, params: dict[str, Any]) -> str:
        """Safe file name without extension, e.g. 'ISO4762_M6x20'."""

    @abstractmethod
    def dimensions(self, params: dict[str, Any]) -> list[Dimension]: ...

    @abstractmethod
    def notes(self, params: dict[str, Any]) -> list[str]: ...

    @abstractmethod
    def build(self, params: dict[str, Any]) -> Part: ...

    def summary_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "source": self.source,
        }

    def describe_json(self) -> dict[str, Any]:
        return {
            **self.summary_json(),
            "parameters": [p.to_json() for p in self.parameters()],
        }
