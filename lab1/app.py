import os
import json
import streamlit as st
from classes import parse_json, draw_er_diagram
from AI_integration import generate_er_json_from_text

st.set_page_config(page_title="ER Diagram Generator", page_icon="📊", layout="wide")

st.title("📊 AI-Powered ER Diagram Generator")
st.markdown("Generate Chen-notation ER Diagrams from **Structured JSON (Part 1)** or **Plain-Text Requirements (Part 2)**.")

# Sidebar for Gemini API Key
with st.sidebar:
    st.header("⚙️ Configuration")
    env_key = os.environ.get("GEMINI_API_KEY", "")
    api_key = st.text_input(
        "Gemini API Key (for Part 2)",
        value=env_key,
        type="password",
        help="Required only when generating ER diagrams from plain text."
    )
    output_name = st.text_input("Output File Base Name", value="er_diagram_output")

# Create two tabs for the two input modes
tab_text, tab_json = st.tabs(["✨ Part 2: Plain-Text Description (AI)", "📄 Part 1: Structured JSON"])

# ==========================================
# TAB 1: Plain-Text Description (Gemini API)
# ==========================================
with tab_text:
    st.subheader("Describe your database system in plain English")
    default_desc = (
        "Design a database for a university. We need to store Students, where each student has a "
        "unique StudentID, a full Name (FirstName, LastName), multiple Email addresses, and a Major. "
        "We also have Courses, identified by a unique CourseCode, along with a Title and Credits. "
        "Students enroll in many Courses, and each Course can have many Students."
    )
    user_description = st.text_area("System Description:", value=default_desc, height=160)

    if st.button("🚀 Generate JSON & ER Diagram with AI", type="primary"):
        if not api_key:
            st.error("Please enter your Gemini API Key in the left sidebar first!")
        elif not user_description.strip():
            st.warning("Please enter a system description.")
        else:
            with st.spinner("Analyzing requirements with Gemini AI and rendering diagram..."):
                try:
                    json_path = f"{output_name}.json"
                    # Step 1: Call Gemini API
                    er_dict = generate_er_json_from_text(
                        system_description=user_description,
                        output_json_path=json_path,
                        api_key=api_key
                    )
                    # Step 2: Parse & Draw
                    entities, relationships = parse_json(json_path, is_file=True)
                    png_path = draw_er_diagram(entities, relationships, output_filename=output_name)

                    # Display results side-by-side
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.success("ER Diagram Generated Successfully!")
                        st.image(png_path, caption="Generated ER Diagram (Chen Notation)")
                        with open(png_path, "rb") as img_file:
                            st.download_button("⬇️ Download PNG", data=img_file, file_name=os.path.basename(png_path), mime="image/png")
                    with col2:
                        st.subheader("Generated JSON Schema")
                        st.json(er_dict)
                        st.download_button(
                            "⬇️ Download JSON",
                            data=json.dumps(er_dict, indent=2),
                            file_name=json_path,
                            mime="application/json"
                        )
                except Exception as e:
                    st.error(f"Error: {e}")

# ==========================================
# TAB 2: Direct JSON Input or File Upload
# ==========================================
with tab_json:
    st.subheader("Upload a `.json` file or paste JSON directly")
    uploaded_file = st.file_uploader("Upload JSON file", type=["json"])

    default_json = """{
  "entities": [
    {
      "name": "Employee",
      "attributes": [
        { "name": "SSN", "isPrimaryKey": true },
        { "name": "Name", "composite": ["FirstName", "LastName"] },
        { "name": "Phone", "isMultiValued": true }
      ]
    },
    {
      "name": "Department",
      "attributes": [
        { "name": "DeptID", "isPrimaryKey": true },
        { "name": "Name" }
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
}"""

    if uploaded_file is not None:
        json_text = uploaded_file.read().decode("utf-8")
    else:
        json_text = default_json

    json_input_area = st.text_area("JSON Schema Editor:", value=json_text, height=260)

    if st.button("🎨 Render ER Diagram from JSON", type="primary"):
        try:
            entities, relationships = parse_json(json_input_area, is_file=False)
            png_path = draw_er_diagram(entities, relationships, output_filename=output_name)

            st.success(f"Saved to `{png_path}`!")
            st.image(png_path, caption="Rendered ER Diagram")
            with open(png_path, "rb") as img_file:
                st.download_button("⬇️ Download PNG", data=img_file, file_name=os.path.basename(png_path), mime="image/png")
        except Exception as e:
            st.error(f"Invalid JSON or Schema Error: {e}")