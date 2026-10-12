#  AI-Powered ER Diagram Generator

A Python tool and Streamlit web application that automatically generates Entity-Relationship (ER) diagrams in **Chen notation** from either a **Structured JSON file** or a **Plain-Text Description** using the **Google Gemini API**.

---

##  Features

* **Part 1 — JSON to ER Diagram (`classes.py`):**
  * Validates JSON schemas using **Pydantic** models.
  * Renders visual ER diagrams using **Graphviz**:
    * **Entities:** Rectangles (`box`)
    * **Simple Attributes:** Ovals (`ellipse`)
    * **Primary Key Attributes:** Underlined text
    * **Multi-Valued Attributes:** Double-bordered ovals
    * **Composite Attributes:** Connected sub-attribute ovals
    * **Relationships:** Diamonds with cardinality labels (`1:1`, `1:N`, `N:1`, `M:N`)
    * **Participation Constraints:** Double lines for **Total** participation and single lines for **Partial** participation.

* **Part 2 — Plain Text to ER Diagram via AI (`AI_integration.py`):**
  * Uses the **Gemini API** (`google-genai`) with structured outputs to convert English database descriptions into valid JSON schemas.
  * Includes automatic model fallback (`gemini-2.5-flash` $\rightarrow$ `gemini-2.5-flash-lite` $\rightarrow$ `gemini-2.0-flash`) to handle high-demand traffic spikes.

* **Web GUI (`app.py`):**
  * Built with **Streamlit** for an interactive interface supporting both AI text prompts and direct JSON input/file uploads.
  * Allows instant preview and downloading of the generated `.png` diagram and `.json` schema.

---



---

##  Getting Started (Local Setup)

### 1. Prerequisites
* **Python 3.10+**
* **Graphviz System Binary:**
  * **Windows:** Run `winget install Graphviz.Graphviz` or download from [graphviz.org](https://graphviz.org/download/).
  * **Linux/macOS:** Run `sudo apt-get install graphviz` or `brew install graphviz`.

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Your Gemini API Key
Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey) and set it in your terminal (or enter it directly in the app sidebar):
```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

### 4. Run the Application
* **Run the Streamlit Web GUI:**
  ```bash
  streamlit run lab1/app.py
  ```
* **Run Part 1 (JSON Renderer Only):**
  ```bash
  python lab1/classes.py
  ```
* **Run Part 2 (CLI End-to-End AI Test):**
  ```bash
  python lab1/AI_integration.py
  ```