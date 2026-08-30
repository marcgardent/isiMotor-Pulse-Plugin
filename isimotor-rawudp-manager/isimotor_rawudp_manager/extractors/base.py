"""
Base extractor classes and presentation formatting helpers.
"""

from abc import ABC, abstractmethod
from typing import Any

# Type alias for table row representation: (key, raw_value, formatted_markup, description)
TableRow = tuple[str, Any, str, str]


def format_value(val: Any) -> str:
    """Formats Python values cleanly for UI table presentation with Rich color tags."""
    if val is None:
        return "[dim]-[/dim]"
    if isinstance(val, bool):
        return f"[bold {'#3fb950' if val else '#f85149'}]{val}[/]"
    if isinstance(val, float):
        return f"[bold #e3b341]{val:.4f}[/]"
    if isinstance(val, int):
        return f"[bold #58a6ff]{val}[/]"
    if isinstance(val, str):
        return f'[#a5d6ff]"{val}"[/]' if val else '[dim]""[/dim]'
    if isinstance(val, (list, tuple)):
        items_str = ", ".join(f"{x:.2f}" if isinstance(x, float) else str(x) for x in val)
        return f"({items_str})"
    return str(val)


def model_to_clean_dict(obj: Any) -> dict[str, Any]:
    """Recursively converts dataclasses/models to clean JSON-serializable dictionaries."""
    if obj is None:
        return {}
    if hasattr(obj, "__dataclass_fields__"):
        res: dict[str, Any] = {}
        for f in obj.__dataclass_fields__:
            val = getattr(obj, f)
            if hasattr(val, "__dataclass_fields__"):
                res[f] = model_to_clean_dict(val)
            elif isinstance(val, (list, tuple)):
                res[f] = [model_to_clean_dict(x) if hasattr(x, "__dataclass_fields__") else x for x in val]
            else:
                res[f] = val
        return res
    if isinstance(obj, dict):
        return dict(obj)
    return {"value": str(obj)}


class BaseExtractor(ABC):
    """Abstract base class for packet data and state row extractors."""

    @abstractmethod
    def extract(self, *args: Any, **kwargs: Any) -> list[TableRow]:
        """Extracts structured table rows (key, raw_value, formatted_markup, description)."""
        raise NotImplementedError

    def to_dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Converts underlying model or extracted data to a clean dictionary for JSON export."""
        rows = self.extract(*args, **kwargs)
        return {k: raw for k, raw, _, _ in rows}
