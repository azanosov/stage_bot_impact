"""
ConfigTable class for the IAA RPA Framework.

Wraps the list of row dicts returned by the portal config table API and
provides helper methods for row lookup, value access, and validation.

Usage:
    table = agent.get_config_table("ATOLetters")
    if table is None:
        raise RPASystemException("Could not load ATOLetters config table")

    row = table.get_row("ATO Subject", subject)
    template = table.get_value("ATO Subject", subject, "Template File Name")
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfigTable:
    """
    A config table retrieved from the portal.

    Behaves like a list — supports iteration, indexing, len(), and bool() —
    while also providing named lookup helpers so developers do not need to
    write boilerplate ``next()`` expressions.
    """

    rows: list[dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_list(cls, rows: list[dict[str, Any]]) -> "ConfigTable":
        """Create a ConfigTable from the raw list of row dicts."""
        return cls(rows=rows)

    # ------------------------------------------------------------------
    # Row lookup
    # ------------------------------------------------------------------

    def get_row(self, key_field: str, key_value: Any) -> dict[str, Any] | None:
        """
        Return the first row where ``key_field == key_value``, or ``None``.

        Args:
            key_field:  The field name to match on (e.g. ``"ATO Subject"``).
            key_value:  The value to look up.

        Returns:
            The matching row dict, or ``None`` if not found.
        """
        return next((row for row in self.rows if row.get(key_field) == key_value), None)

    def get_rows(self, key_field: str, key_value: Any) -> list[dict[str, Any]]:
        """
        Return all rows where ``key_field == key_value``.

        Args:
            key_field:  The field name to match on.
            key_value:  The value to filter by.

        Returns:
            A (possibly empty) list of matching row dicts.
        """
        return [row for row in self.rows if row.get(key_field) == key_value]

    def has_row(self, key_field: str, key_value: Any) -> bool:
        """
        Return ``True`` if at least one row has ``key_field == key_value``.

        Args:
            key_field:  The field name to check.
            key_value:  The value to look for.
        """
        return any(row.get(key_field) == key_value for row in self.rows)

    # ------------------------------------------------------------------
    # Value access
    # ------------------------------------------------------------------

    def get_value(
        self, key_field: str, key_value: Any, value_field: str, default: Any = None
    ) -> Any:
        """
        Return a single field value from the first matching row.

        Shortcut for ``get_row(...)[value_field]`` with a safe default.

        Args:
            key_field:    The field name to match on.
            key_value:    The value to look up.
            value_field:  The field whose value should be returned.
            default:      Value to return if the row or field is not found.

        Returns:
            The field value, or ``default`` if not found.
        """
        row = self.get_row(key_field, key_value)
        if row is None:
            return default
        return row.get(value_field, default)

    def column_values(self, field_name: str) -> list[Any]:
        """
        Return a list of values for a single field across all rows.

        Useful for building dropdowns, validation sets, etc.

        Args:
            field_name:  The field to extract.

        Returns:
            A list of values (``None`` where the field is absent in a row).
        """
        return [row.get(field_name) for row in self.rows]

    # ------------------------------------------------------------------
    # Sequence interface
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.rows[index]

    def __bool__(self) -> bool:
        return bool(self.rows)

    def __repr__(self) -> str:
        return f"ConfigTable({len(self.rows)} rows)"
