import os
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from graphviz import Graph
from pydantic import BaseModel, Field
os.environ["PATH"] += os.pathsep + r"C:\Program Files\Graphviz\bin"

class Attribute(BaseModel):
    name: str = Field(description="Name of the attribute")
    isPrimaryKey: Optional[bool] = Field(
        default=None,
        description="Set to true ONLY if this is a primary key attribute."
    )
    isMultiValued: Optional[bool] = Field(
        default=None,
        description="Set to true ONLY if this attribute can hold multiple values (e.g., Phone, Location)."
    )
    composite: Optional[List[str]] = Field(
        default=None,
        description="List of sub-attribute names ONLY if this is a composite attribute (e.g., ['FirstName', 'LastName'])."
    )

    @property
    def is_composite(self) -> bool:
        return bool(self.composite)


class Entity(BaseModel):
    name: str = Field(description="Singular noun name of the entity (e.g., Employee, Department)")
    attributes: List[Attribute]


class Relationship(BaseModel):
    entity1: str = Field(description="Exact name of the first entity in the relationship")
    entity2: str = Field(description="Exact name of the second entity in the relationship")
    name: str = Field(description="Verb/action name of the relationship (e.g., Works_In, Manages)")
    cardinality: str = Field(description="Cardinality ratio formatted strictly as '1:1', '1:N', 'N:1', or 'M:N'")


class ERDiagramSchema(BaseModel):
    entities: List[Entity]
    relationships: List[Relationship]


def parse_json(json_input: str | Dict[str, Any], is_file:bool = False) -> tuple[List[Entity], List[Relationship]]:
    if is_file:
        with open(json_input, "r", encoding="utf-8") as f:
            raw_json = f.read()
        schema = ERDiagramSchema.model_validate_json(raw_json) #.json file
    elif isinstance(json_input, str):
        schema = ERDiagramSchema.model_validate_json(json_input) # raw json
    else:
        schema = ERDiagramSchema.model_validate(json_input) # python dict
    return schema.entities, schema.relationships


def draw_er_diagram(entities : List[Entity], relationships: List[Relationship], output_filename:str) -> str:
    dot = Graph(name="ER_Diagram", format="png", engine="dot")
    dot.attr(rankdir="LR", nodesep="0.4", ranksep="0.8", fontname="Helvetica")
    dot.attr("node", fontname="Helvetica", fontsize="11")
    dot.attr("edge", fontname="Helvetica", fontsize="10")

    for entity in entities:
        ent_id = f"ent_{entity.name}"
        dot.node(
            ent_id,
            label=entity.name,
            shape="box",
            style="filled",
            fillcolor="#E8F0FE"
        )

        for attr in entity.attributes:
            attr_id = f"attr_{entity.name}_{attr.name}"
            label = f"<<U>{attr.name}</U>>" if attr.isPrimaryKey else attr.name
            peripheries = "2" if attr.isMultiValued else "1"

            dot.node(
                attr_id,
                label=label,
                shape="ellipse",
                peripheries=peripheries
            )
            dot.edge(ent_id, attr_id)

            if attr.is_composite:
                for sub_attr in attr.composite:
                    sub_id = f"sub_{entity.name}_{attr.name}_{sub_attr}"
                    dot.node(sub_id, label=sub_attr, shape="ellipse", fontsize="9")
                    dot.edge(attr_id, sub_id)

    for i, rel in enumerate(relationships):
            rel_id = f"rel_{i}_{rel.name}" # use i because if 2 relations have the same name
            dot.node(
                rel_id,
                label=rel.name,
                shape="diamond",
                style="filled",
                fillcolor="#FEF7E0"
            )

            if ":" in rel.cardinality:
                card1, card2 = rel.cardinality.split(":", 1)
            else:
                card1, card2 = rel.cardinality, ""

            dot.edge(f"ent_{rel.entity1}", rel_id, label=f" {card1} ")
            dot.edge(rel_id, f"ent_{rel.entity2}", label=f" {card2} ")

    saved_path = dot.render(filename=output_filename, cleanup=True)
    return saved_path




if __name__ == "__main__":
    sample_json = """
    {
      "entities": [
        {
          "name": "Employee",
          "attributes": [
            { "name": "SSN", "isPrimaryKey": true },
            { "name": "Name", "composite": ["FirstName", "LastName"] },
            { "name": "Phone", "isMultiValued": true },
            { "name": "Address", "composite": ["Street", "City", "State", "ZIP"] }
          ]
        },
        {
          "name": "Department",
          "attributes": [
            { "name": "DeptID", "isPrimaryKey": true },
            { "name": "Name" },
            { "name": "Location", "isMultiValued": true }
          ]
        }
      ],
      "relationships": [
        {
          "entity1": "Employee",
          "entity2": "Department",
          "name": "Works_In",
          "cardinality": "N:1"
        }
      ]
    }
    """
    entities, relationships = parse_json(sample_json)
    output_file = draw_er_diagram(entities, relationships, output_filename="er_diagram")
    print(f"Done! Saved ER diagram to: {output_file}")