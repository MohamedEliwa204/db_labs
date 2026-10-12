import json
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass # hold structured data
class Attribute:
    name: str
    is_primary_key: bool = False
    is_multi_valued: bool = False
    composite: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Attribute':
        return cls(
            name=data["name"],
            is_primary_key=data.get("isPrimaryKey", False),
            is_multi_valued=data.get("isMultiValued", False),
            composite=data.get("composite", [])
        )

    @property
    def is_composite(self) -> bool:  # still like attribute not method
        return len(self.composite) > 0


@dataclass
class Entity:
    name: str
    attributes: List[Attribute] = field(default_factory=list)  # to create new list in memory for each instance

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Entity':
        attributes = [
            Attribute.from_dict(attr) for attr in data.get("attributes", [])
        ]
        return cls(name=data["name"], attributes=attributes)


@dataclass
class Relationship:
    entity1: str
    entity2: str
    name: str
    cardinality: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Relationship':
        return cls(
            name=data["name"],
            entity1=data["entity1"],
            entity2=data["entity2"],
            cardinality=data["cardinality"]
        )




def parse_json(json_input: str | Dict[str, Any], is_file:bool = False) -> tuple[List[Entity], List[Relationship]]:
    if is_file:
        with open(json_input, 'r', encoding='utf-8') as file: # json file
            data = json.load(file)

    elif isinstance(json_input, str): # raw json
        data = json.loads(json_input)
    else:                             # python dict
        data = json_input


    entities = [Entity.from_dict(ent) for ent in data.get("entities", [])]
    relationships = [Relationship.from_dict(rel) for rel in data.get("relationships", [])]
    return entities, relationships

