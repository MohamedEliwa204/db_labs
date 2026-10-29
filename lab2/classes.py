
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
import json
from typing import Tuple, List, Union, Dict, Any
@dataclass
class Attribute:
    name: str
    is_primary_key: bool = False  # For weak entities, this acts as the partial key
    is_multivalued: bool = False
    composite: List[str] = field(default_factory=list)

@dataclass
class Entity:
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    is_weak: bool = False        # Edge case: Step 2
    owner_entity: str = None     # Edge case: Step 2

@dataclass
class Relationship:
    name: str
    cardinality: str  # "1:1", "1:N", "N:1", "M:N", or "N-ary"
    participating_entities: List[str] = field(default_factory=list)
    attributes: List[Attribute] = field(default_factory=list)

@dataclass
class Table:
    name: str
    columns: List[str] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: List[Tuple[str, str, str]] = field(default_factory=list)

    def add_column(self, col_name: str, is_pk: bool = False):
        if col_name not in self.columns:
            self.columns.append(col_name)
        if is_pk and col_name not in self.primary_keys:
            self.primary_keys.append(col_name)

    def add_foreign_key(self, col_name: str, ref_table: str, ref_column: str):
        if col_name not in self.columns:
            self.columns.append(col_name)
        self.foreign_keys.append((col_name, ref_table, ref_column))


def parse_erd_json(input_data: Union[str, Dict[str, Any]]) -> Tuple[List[Entity], List[Relationship]]:
    if isinstance(input_data, dict):
        data = input_data
    elif isinstance(input_data, str):
        input_str = input_data.strip()
        # If it starts with '{', treat it as a raw JSON string
        if input_str.startswith('{'):
            data = json.loads(input_str)
        else:
            with open(input_data, 'r', encoding='utf-8') as file:
                data = json.load(file)
    else:
        raise ValueError("input_data must be a dictionary, a JSON string, or a file path.")

    entities = []
    for ent_data in data.get("entities", []):
        attributes = []
        for attr_data in ent_data.get("attributes", []):
            attributes.append(Attribute(
                name=attr_data.get("name"),
                is_primary_key=attr_data.get("isPrimaryKey", False),
                is_multivalued=attr_data.get("isMultiValued", False),
                composite=attr_data.get("composite", [])
            ))
        entities.append(Entity(
            name=ent_data.get("name"),
            attributes=attributes,
            # Capture weak entity properties
            is_weak=ent_data.get("isWeak", False),
            owner_entity=ent_data.get("ownerEntity")
        ))

    relationships = []
    for rel_data in data.get("relationships", []):
        # Extract relationship attributes if they exist
        attributes = []
        for attr_data in rel_data.get("attributes", []):
            attributes.append(Attribute(
                name=attr_data.get("name"),
                is_primary_key=attr_data.get("isPrimaryKey", False),
                is_multivalued=attr_data.get("isMultiValued", False),
                composite=attr_data.get("composite", [])
            ))

        # Support both explicit list format and legacy entity1/entity2 format
        participating_entities = rel_data.get("participatingEntities", [])
        if not participating_entities:
            ent1 = rel_data.get("entity1")
            ent2 = rel_data.get("entity2")
            if ent1 and ent2:
                participating_entities = [ent1, ent2]

        relationships.append(Relationship(
            name=rel_data.get("name"),
            cardinality=rel_data.get("cardinality"),
            participating_entities=participating_entities,
            attributes=attributes
        ))

    return entities, relationships


def map_er_to_relational(entities: List[Entity], relationships: List[Relationship]) -> List[Table]:
    tables: Dict[str, Table] = {}


    def process_attributes(table: Table, attrs: List[Attribute]):
        for attr in attrs:
            if attr.is_multivalued:
                continue  # Handled in Step 6
            elif attr.composite:
                for sub_attr in attr.composite:
                    table.add_column(sub_attr, is_pk=attr.is_primary_key)
            else:
                table.add_column(attr.name, is_pk=attr.is_primary_key)

    # Step 1: Mapping of Regular (strong) Entity Types
    for entity in [e for e in entities if not e.is_weak]:
        table = Table(name=entity.name)
        process_attributes(table, entity.attributes)
        tables[entity.name] = table

    # Step 2: Mapping of Weak Entity Types
    for entity in [e for e in entities if e.is_weak]:
        table = Table(name=entity.name)
        process_attributes(table, entity.attributes)

        # Include as foreign key the PK of the owner entity
        if entity.owner_entity and entity.owner_entity in tables:
            owner_table = tables[entity.owner_entity]
            for owner_pk in owner_table.primary_keys:
                fk_name = f"{owner_table.name}_{owner_pk}"
                table.add_foreign_key(fk_name, owner_table.name, owner_pk)
                table.primary_keys.append(fk_name)

        tables[entity.name] = table

    # Step 6: Mapping of Multivalued attributes
    for entity in entities:
        parent_table = tables[entity.name]
        for attr in entity.attributes:
            if attr.is_multivalued:
                mv_table = Table(name=f"{entity.name}_{attr.name}")

                # Add parent PK as FK
                for pk in parent_table.primary_keys:
                    fk_name = f"{parent_table.name}_{pk}"
                    mv_table.add_foreign_key(fk_name, parent_table.name, pk)
                    mv_table.add_column(fk_name, is_pk=True)

                # Include the attribute itself (handling composites if any)
                if attr.composite:
                    for sub in attr.composite:
                        mv_table.add_column(sub, is_pk=True)
                else:
                    mv_table.add_column(attr.name, is_pk=True)

                tables[mv_table.name] = mv_table

    # Process Relationships (Steps 3, 4, 5, 7)
    for rel in relationships:
        # Step 7: Mapping of N-ary Relationship Types (n > 2)
        if len(rel.participating_entities) > 2:
            rel_table = Table(name=rel.name)
            for ent_name in rel.participating_entities:
                ent_table = tables[ent_name]
                for pk in ent_table.primary_keys:
                    fk_name = f"{ent_name}_{pk}"
                    rel_table.add_foreign_key(fk_name, ent_table.name, pk)
                    rel_table.add_column(fk_name, is_pk=True)  # Combination is PK
            process_attributes(rel_table, rel.attributes)
            tables[rel_table.name] = rel_table
            continue

        # Binary Relationships
        ent1, ent2 = rel.participating_entities[0], rel.participating_entities[1]

        # Step 3: Mapping of Binary 1:1 Relation Types
        if rel.cardinality == "1:1":
            s_table, t_table = tables[ent1], tables[ent2]
            for pk in t_table.primary_keys:
                s_table.add_foreign_key(f"{t_table.name}_{pk}", t_table.name, pk)
            process_attributes(s_table, rel.attributes)

        # Step 4: Mapping of Binary 1:N Relationship Types
        elif rel.cardinality in ["1:N", "N:1"]:
            n_side = ent2 if rel.cardinality == "1:N" else ent1
            one_side = ent1 if rel.cardinality == "1:N" else ent2

            n_table = tables[n_side]
            one_table = tables[one_side]
            for pk in one_table.primary_keys:
                n_table.add_foreign_key(f"{one_table.name}_{pk}", one_table.name, pk)

            # Include simple attributes of the relationship in N-side
            process_attributes(n_table, rel.attributes)

        # Step 5: Mapping of Binary M:N Relationship Types
        elif rel.cardinality == "M:N":
            # Create a new relationship relation
            rel_table = Table(name=rel.name)

            # Include PKs as FKs
            for ent_name in [ent1, ent2]:
                ent_table = tables[ent_name]
                for pk in ent_table.primary_keys:
                    fk_name = f"{ent_name}_{pk}"
                    rel_table.add_foreign_key(fk_name, ent_table.name, pk)
                    rel_table.add_column(fk_name, is_pk=True)  # Combination is PK

            # Include relationship attributes
            process_attributes(rel_table, rel.attributes)
            tables[rel_table.name] = rel_table

    return list(tables.values())