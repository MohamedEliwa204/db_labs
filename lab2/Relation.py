import json
from typing import List, Dict, Any, Callable, Tuple


class Relation:
    def __init__(self, name: str, rows: List[Dict[str, Any]]):
        self.name = name

        self.rows = self._deduplicate(rows)
        self.columns = list(self.rows[0].keys()) if self.rows else []

    def _deduplicate(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Helper: Removes duplicate rows by converting dicts to hashable frozensets."""
        seen = set()
        unique_rows = []
        for row in rows:
            # Sort items to ensure consistent hashing
            hashed_row = frozenset(row.items())
            if hashed_row not in seen:
                seen.add(hashed_row)
                unique_rows.append(row)
        return unique_rows

    def _hashable_rows(self) -> set:
        """Helper: Returns rows as a set of frozensets for fast set operations."""
        return {frozenset(row.items()) for row in self.rows}


    def project(self, columns: List[str]) -> 'Relation':
        missing = [col for col in columns if col not in self.columns]
        if missing:
            raise ValueError(f"Columns {missing} not found in relation {self.name}")
        new_rows = [{col: row[col] for col in columns} for row in self.rows]
        return Relation(f"π_{','.join(columns)}({self.name})", new_rows)

    def select(self, condition: Callable[[Dict[str, Any]], bool], condition_str: str = "") -> 'Relation':
        new_rows = [row for row in self.rows if condition(row)]
        name_suffix = condition_str if condition_str else "condition"
        return Relation(f"σ_{name_suffix}({self.name})", new_rows)


    def _check_compatibility(self, other: 'Relation'):
        if set(self.columns) != set(other.columns):
            raise ValueError("Relations are not union-compatible (different columns).")

    def union(self, other: 'Relation') -> 'Relation':
        self._check_compatibility(other)
        self_set = self._hashable_rows()
        other_set = other._hashable_rows()
        union_set = self_set.union(other_set)
        new_rows = [dict(row) for row in union_set]
        return Relation(f"{self.name} ∪ {other.name}", new_rows)

    def intersect(self, other: 'Relation') -> 'Relation':
        self._check_compatibility(other)
        self_set = self._hashable_rows()
        other_set = other._hashable_rows()
        intersect_set = self_set.intersection(other_set)
        new_rows = [dict(row) for row in intersect_set]
        return Relation(f"{self.name} ∩ {other.name}", new_rows)

    def difference(self, other: 'Relation') -> 'Relation':
        self._check_compatibility(other)
        self_set = self._hashable_rows()
        other_set = other._hashable_rows()
        diff_set = self_set.difference(other_set)
        new_rows = [dict(row) for row in diff_set]
        return Relation(f"{self.name} - {other.name}", new_rows)

    def display(self):
        if not self.rows:
            print(f"\nEmpty Relation: {self.name}")
            return
        col_widths = {col: max(len(col), max((len(str(row.get(col, ""))) for row in self.rows), default=0)) for col in
                      self.columns}
        header = " | ".join(col.ljust(col_widths[col]) for col in self.columns)

        print(f"\n--- Result: {self.name} ---")
        print(header)
        print("-" * len(header))
        for row in self.rows:
            print(" | ".join(str(row.get(col, "")).ljust(col_widths[col]) for col in self.columns))
        print("-" * len(header))