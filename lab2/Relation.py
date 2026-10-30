import json
from typing import List, Dict, Any, Callable, Tuple


class Relation:
    def __init__(self, name: str, rows: List[Dict[str, Any]]):
        self.name = name

        self.rows = self._deduplicate(rows)
        self.columns = list(self.rows[0].keys()) if self.rows else []

    def _deduplicate(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique_rows = []
        for row in rows:
            hashed_row = frozenset(row.items())
            if hashed_row not in seen:
                seen.add(hashed_row)
                unique_rows.append(row)
        return unique_rows

    def _hashable_rows(self) -> set:
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

    def join(self, other: 'Relation', condition: Callable[[Dict[str, Any], Dict[str, Any]], bool],
             condition_str: str = "") -> 'Relation':
        new_rows = []
        overlapping_cols = set(self.columns).intersection(other.columns)
        for row1 in self.rows:
            for row2 in other.rows:
                if condition(row1, row2):
                    merged_row = {}
                    # Safely insert values, prefixing if there is a collision
                    for col, val in row1.items():
                        resolved_col = f"{self.name}.{col}" if col in overlapping_cols else col
                        merged_row[resolved_col] = val
                    for col, val in row2.items():
                        resolved_col = f"{other.name}.{col}" if col in overlapping_cols else col
                        merged_row[resolved_col] = val

                    new_rows.append(merged_row)

        name_suffix = condition_str if condition_str else "condition"
        return Relation(f"{self.name} ⋈_{name_suffix} {other.name}", new_rows)

    def natural_join(self, other: 'Relation') -> 'Relation':
        new_rows = []
        common_cols = set(self.columns).intersection(other.columns)
        # If there are no common columns, it degenerates into a Cartesian Product
        if not common_cols:
            for row1 in self.rows:
                for row2 in other.rows:
                    new_rows.append({**row1, **row2})
            return Relation(f"{self.name} ⨯ {other.name}", new_rows)
        for row1 in self.rows:
            for row2 in other.rows:
                if all(row1[col] == row2[col] for col in common_cols):
                    merged_row = {**row1, **row2}
                    new_rows.append(merged_row)

        return Relation(f"{self.name} * {other.name}", new_rows)

    def left_join(self, other: 'Relation', condition: Callable[[Dict[str, Any], Dict[str, Any]], bool],
                  condition_str: str = "") -> 'Relation':
        new_rows = []
        overlapping_cols = set(self.columns).intersection(other.columns)

        for row1 in self.rows:
            matched = False
            for row2 in other.rows:
                if condition(row1, row2):
                    matched = True
                    merged_row = {}
                    for col, val in row1.items():
                        resolved_col = f"{self.name}.{col}" if col in overlapping_cols else col
                        merged_row[resolved_col] = val
                    for col, val in row2.items():
                        resolved_col = f"{other.name}.{col}" if col in overlapping_cols else col
                        merged_row[resolved_col] = val
                    new_rows.append(merged_row)


            if not matched:
                merged_row = {}
                for col, val in row1.items():
                    resolved_col = f"{self.name}.{col}" if col in overlapping_cols else col
                    merged_row[resolved_col] = val
                for col in other.columns:
                    resolved_col = f"{other.name}.{col}" if col in overlapping_cols else col
                    merged_row[resolved_col] = None
                new_rows.append(merged_row)

        name_suffix = condition_str if condition_str else "condition"
        return Relation(f"{self.name} ⟕_{name_suffix} {other.name}", new_rows)

    def right_join(self, other: 'Relation', condition: Callable[[Dict[str, Any], Dict[str, Any]], bool],
                   condition_str: str = "") -> 'Relation':
        new_rows = []
        overlapping_cols = set(self.columns).intersection(other.columns)
        for row2 in other.rows:
            matched = False
            for row1 in self.rows:
                if condition(row1, row2):
                    matched = True
                    merged_row = {}
                    for col, val in row1.items():
                        resolved_col = f"{self.name}.{col}" if col in overlapping_cols else col
                        merged_row[resolved_col] = val
                    for col, val in row2.items():
                        resolved_col = f"{other.name}.{col}" if col in overlapping_cols else col
                        merged_row[resolved_col] = val
                    new_rows.append(merged_row)

            if not matched:
                merged_row = {}
                for col in self.columns:
                    resolved_col = f"{self.name}.{col}" if col in overlapping_cols else col
                    merged_row[resolved_col] = None
                for col, val in row2.items():
                    resolved_col = f"{other.name}.{col}" if col in overlapping_cols else col
                    merged_row[resolved_col] = val
                new_rows.append(merged_row)

        name_suffix = condition_str if condition_str else "condition"
        return Relation(f"{self.name} ⟖_{name_suffix} {other.name}", new_rows)

    from typing import List, Tuple, Dict, Any

    def aggregate(self, group_by_cols: List[str], aggregations: List[Tuple[str, str]]) -> 'Relation':
        # Validate columns
        for col in group_by_cols:
            if col not in self.columns:
                raise ValueError(f"Group by column '{col}' not found in relation {self.name}")
        for agg_func, agg_col in aggregations:
            if agg_col not in self.columns and agg_col != "*":
                raise ValueError(f"Aggregate column '{agg_col}' not found in relation {self.name}")

        agg_names = ",".join([f"{func.upper()}({col})" for func, col in aggregations])
        group_cols = ",".join([f"({col})" for  col in group_by_cols])
        new_rel_name = f"{group_cols}_γ_{agg_names}({self.name})"

        # Edge case 1: Empty relation
        if not self.rows:
            return Relation(new_rel_name, [])

        # Grouping Phase: Store entire rows instead of single values
        grouped = {}
        for row in self.rows:
            # Edge case 2: Global aggregation (empty group_by_cols) -> use a constant key
            key = tuple(row.get(col) for col in group_by_cols) if group_by_cols else ("_global_",)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(row)

        # Calculation Phase
        new_rows = []
        for key, rows_in_group in grouped.items():
            new_row = {}
            if group_by_cols:
                new_row = dict(zip(group_by_cols, key))
            for agg_func, agg_col in aggregations:
                agg_upper = agg_func.upper()

                if agg_col == "*":
                    # Special case to support COUNT(*)
                    values = rows_in_group
                else:
                    values = [r.get(agg_col) for r in rows_in_group if r.get(agg_col) is not None]

                result = None
                if agg_upper == 'COUNT':
                    result = len(values)
                elif values:
                    numeric_vals = [v for v in values if isinstance(v, (int, float))]
                    if agg_upper == 'SUM':
                        result = sum(numeric_vals)
                    elif agg_upper == 'AVG':
                        result = sum(numeric_vals) / len(numeric_vals) if numeric_vals else None
                    elif agg_upper == 'MAX':
                        result = max(values)
                    elif agg_upper == 'MIN':
                        result = min(values)
                    else:
                        raise ValueError(f"Unsupported aggregate function: {agg_func}")
                else:
                    # If all values were None, COUNT is 0, others are None
                    if agg_upper != 'COUNT':
                        result = None
                new_col_name = f"{agg_upper}({agg_col})"
                new_row[new_col_name] = result
            new_rows.append(new_row)
        return Relation(new_rel_name, new_rows)