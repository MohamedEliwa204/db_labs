import json
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Attribute:
    name: str
    is_primary_key: bool = False
    is_multi_valued: bool = False
    composite: List[str] = field(default_factory=list)

    def __init__(self, data: dict):
        self.name = data["name"]
        self.is_primary_key = data.get("isPrimaryKey", False)
        self.is_multi_valued = data.get("isMultiValued", False)
        self.composite = data.get("composite", [])

    @property
    def is_composite(self) -> bool:  # still like attribute not method
        return len(self.composite) > 0


@dataclass
class Entity:
    name: str
    attributes: List[Attribute] = field(default_factory=list)  # to create new list in memory for each instance

    def __init__(self, data: dict):
        self.name = data["name"]
        self.attributes = [Attribute(attr) for attr in data.get("attributes", [])]


@dataclass
class Relationship:
    entity1: str
    entity2: str
    name: str
    cardinality: str

    def __init__(self, data: dict):
        self.name = data["name"]
        self.entity1 = data["entity1"]
        self.entity2 = data["entity2"]
        self.cardinality = data["cardinality"]




def parse_json(json_input: str | Dict[str, Any], is_file:bool = False) -> tuple[List[Entity], List[Relationship]]:
    if is_file:
        with open(json_input, 'r', encoding='utf-8') as file: # json file
            data = json.load(file)

    elif isinstance(json_input, str): # raw json
        data = json.laods(json_input)
    else:                             # python dict
        data = json_input


    entities = [Entity(ent) for ent in data.get("entities", [])]
    relationships = [Relationship(rel) for rel in data.get("relationships", [])]
    return entities, relationships

