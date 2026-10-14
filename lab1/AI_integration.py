import os
import json
from google import genai
from google.genai import types
from google.genai.errors import APIError
import time
from classes import parse_json, draw_er_diagram, ERDiagramSchema


def generate_er_json_from_text(system_description:str, output_json_path:str, api_key: str) -> dict:
    client = genai.Client(api_key=api_key)

    system_prompt = """
        You are an expert Database Architect. Analyze the user's plain-text system description
        and extract an Entity-Relationship (ER) model.

        Output ONLY a valid JSON object matching this exact structure:
        {
          "entities": [
            {
              "name": "EntityName",
              "attributes": [
                { "name": "PrimaryKeyAttr", "isPrimaryKey": true },
                { "name": "SimpleAttr" },
                { "name": "MultiValuedAttr", "isMultiValued": true },
                { "name": "CompositeAttr", "composite": ["SubAttr1", "SubAttr2"] }
              ]
            }
          ],
          "relationships": [
            {
              "entity1": "EntityName1",
              "entity2": "EntityName2",
              "name": "RelationshipName",
              "cardinality": "1:1 | 1:N | N:1 | M:N",
              "participation1": "total | partial",
              "participation2": "total | partial"
            }
          ]
        }

        Strict Rules:
        1. Every entity MUST have at least one attribute with "isPrimaryKey": true.
        2. Only include "isPrimaryKey": true when the attribute is a primary key. Omit it otherwise.
        3. Only include "isMultiValued": true when an attribute can hold multiple values. Omit it otherwise.
        4. Only include "composite": [...] when an attribute is composed of sub-parts. Omit it otherwise.
        5. In "relationships", "entity1" and "entity2" MUST exactly match the "name" of an entity defined in the "entities" list.
        6. "cardinality" MUST be formatted with a colon, such as "1:1", "1:N", "N:1", or "M:N".
        7. Set "participation1" (for entity1) and "participation2" (for entity2) to "total" if every instance of that entity MUST participate in the relationship (e.g., "every employee must work in a department"), or "partial" if participation is optional (e.g., "an employee may manage a department").
        8. If an entity cannot be uniquely identified without another entity, set "isWeak": true on that entity.
        9. For weak entities, mark their discriminator attribute with "isPartialKey": true instead of "isPrimaryKey".
        10. If a relationship connects a weak entity to its strong owner entity, set "isIdentifying": true on that relationship.
        """

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
    ]

    last_error = None
    response = None

    for model_name in models_to_try:
        try:
            print(f"Trying model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=f"Extract an ER diagram schema from this description:\n{system_description}",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=ERDiagramSchema,
                    temperature=0.1,
                ),
            )
            break
        except APIError as e:
            last_error = e
            if e.code in (503, 429):
                print(f"[{model_name}] busy (HTTP {e.code}), switching to fallback model...")
                time.sleep(1)
                continue
            else:
                raise e

    if response is None:
        raise RuntimeError(f"All Gemini models are currently busy. Last error: {last_error}")

    er_schema: ERDiagramSchema = response.parsed

    with open(output_json_path, "w", encoding="utf-8") as f:
        f.write(er_schema.model_dump_json(indent=2, exclude_none=True))

    print(f"[Part 2] AI-generated JSON saved to: {output_json_path}")
    return er_schema.model_dump(exclude_none=True)



if __name__ == "__main__":

    API_KEY = os.environ.get("GEMINI_API_KEY")
    university_description = """
    Design a database for a university. 
    We need to store Students, where each student has a unique StudentID, a full Name 
    (broken down into FirstName and LastName), multiple Email addresses, and a Major.
    We also have Courses, identified by a unique CourseCode, along with a Title and Credits.
    Instructors have a unique InstructorID, a Name, multiple Phone numbers, and an Address 
    composed of Building and RoomNumber.
    Students enroll in many Courses, and each Course can have many Students.
    Each Instructor teaches many Courses, but each Course is taught by only one Instructor.
    """

    json_file = "university_er.json"
    png_file = "university_er_diagram"

    generate_er_json_from_text(
        system_description=university_description,
        output_json_path=json_file,
        api_key=API_KEY
    )
    entities, relationships = parse_json(json_file, is_file=True)
    final_image = draw_er_diagram(entities, relationships, output_filename=png_file)
    print(f"[End-to-End Complete] Final ER Diagram generated at: {final_image}")
