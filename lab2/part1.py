import os
if os.name == "nt":
    os.environ["PATH"] += os.pathsep + r"C:\Program Files\Graphviz\bin"

from typing import List
import graphviz
import classes


def generate_dot_diagram(tables: List[classes.Table]) -> str:
    lines = [
        "digraph RelationalModel {",
        "    rankdir=TB;  // Top to bottom layout",
        "    nodesep=0.5; // Spacing between nodes",
        "    ranksep=1.0; // Spacing between ranks",
        "    node [shape=none, fontname=Helvetica, fontsize=10, margin=0];",
        "    edge [fontname=Helvetica, fontsize=10];"
    ]

    # Phase 1: Draw the Table Nodes in a horizontal layout
    for table in tables:
        label = '<<table border="0" cellborder="0" cellspacing="0" cellpadding="2">'
        label += f'<tr><td align="left"><b>{table.name}</b></td></tr>'
        label += '<tr><td>'
        label += '<table border="0" cellborder="1" cellspacing="0" cellpadding="4"><tr>'

        for col in table.columns:
            display_text = col

            if col in table.primary_keys:
                display_text = f"<u>{display_text}</u>"

            is_fk = any(fk[0] == col for fk in table.foreign_keys)
            if is_fk:
                display_text += " (FK)"

            label += f'<td port="{col}" align="center">{display_text}</td>'

        label += '</tr></table>'
        label += '</td></tr></table>>'

        lines.append(f'    {table.name} [label={label}];')

    # Phase 2: Draw the Foreign Key Arrows
    for table in tables:
        for fk_col, ref_table, ref_col in table.foreign_keys:
            # Removed the forced compass points so Graphviz snaps to the closest edge
            lines.append(f'    {table.name}:{fk_col} -> {ref_table}:{ref_col};')

    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    entities, relationships = classes.parse_erd_json("part1_erd_stress_test.json")
    tables = classes.map_er_to_relational(entities, relationships)
    dot_source = generate_dot_diagram(tables)
    graph = graphviz.Source(dot_source)
    graph.render(filename="relational_schema", format="png", cleanup=True)
    print("Schema generated successfully: relational_schema.png")