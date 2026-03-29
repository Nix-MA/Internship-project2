# Lumina Assessment Engine

## 1. Overview

> **See `docs/deep_dive/` for full system explanation.**

The Lumina Assessment Engine is a local-first, privacy-respecting assessment generation pipeline. It solves the laborious process of manually building and grading pedagogically sound tests by dynamically transforming raw multi-modal user documents into highly structured JSON quizzes.

**High-Level Pipeline:**
Input Documents → Parsing & Normalisation → Token-aware Chunking → LLM Prompt Injections → JSON Schema Validation → Interactive User Test → Evaluation via Rubrics → Grading Analytics → PDF/DOCX Report Exports.

## 2. Key Features
- **Multi-format Ingestion:** Supports text formats, Office documents, audio/video extensions, and direct YouTube URLs.
- **Deep Question Generation:** Dynamically spins up 8 unique question types (MCQ, True/False, Fill in Blanks, Match the Following, Assertion/Reason, One Word, Short Answer, Long Answer).
- **Comprehensive Rubric Grading:** Assesses Short/Long answers on exact criteria (Accuracy, Completeness, Conceptual Clarity, Expression).
- **Intelligent Evaluation:** Deploys rapidfuzz matching algorithms for partial credit scoring.
- **Export System:** Renders natively to portable PDF or DOCX file downloads.

## 3. System Architecture
The system is built sequentially to prevent cascading failures. Modules operate strictly within scoped boundaries:

`Input → Ingestion → Chunking → Generation → Validation → Grading → Results`

## 4. Tech Stack
- **Core Engine:** Python 3.10+
- **Frontend / UI:** Streamlit
- **LLM Inferencing:** Ollama (requires local installation)
- **Persistance:** Local SQLite
- **Input Parsing:** `pdfplumber`, `youtube_transcript_api`
- **Output Rendering:** `fpdf2`, `python-docx`
- **Scoring Algorithms:** `rapidfuzz`

## 5. Installation
The environment relies on strict Python 3.10.x bindings. 

```bash
git clone https://github.com/your-org/lumina-assessment.git
cd lumina-assessment

# Initialize a Virtual Environment
python -m venv venv

# Activate Environment (Windows CMD/PowerShell)
venv\Scripts\activate
# Activate Environment (Mac/Linux)
source venv/bin/activate

# Install strictly locked dependencies
pip install -r requirements.txt
```

## 6. Dependencies Requirement
You **must** have a background instance of `ollama serve` running.
Pull the foundational model before booting the interface:
```bash
ollama pull llama3.2
```

## 7. Configuration Precedence
Application boundaries gracefully cascade properties. Modifications execute in this order (Highest precedence to lowest):
1. **System Environment Variables** (Direct terminal bounds e.g. `export LLM__TIMEOUT_SECONDS=180`)
2. **`.env` file variables** (Top level overrides)
3. **`src/config/config.yaml`** (Standard operational defaults)
4. **Pydantic defaults** (In-built failsafe parameters)

## 8. Running the Application
To launch the primary Web Interface:
```bash
streamlit run src/app.py
```
*The instance will boot locally at `http://localhost:8501`*

## 9. CLI Access
A headless pipeline is available for script-kiddy operations via parameter flags without booting Streamlit memory tracking:
```bash
python -m src.main path/to/document.pdf --type "MCQ" --count 5
```

## 10. Usage Flow
- **Upload**: Drag-and-drop your target files or paste a valid YouTube string onto the main entry screen.
- **Generate**: Select the specific subset combinations of your chosen 8 question types and click *Generate*.
- **Answer**: Streamlit displays questions reactively. Input strings or select variables interactively.
- **View Results**: The evaluation orchestrator dumps real-time accuracy percentages aligned beside visual metrics on completion.
- **Export**: Render out the finalised scores cleanly formatted dynamically to either `.pdf` or `.docx`.

## 11. Data Flow (End-to-End)
1. User drops `document.pdf`.
2. `pdfplumber` rips text. Text sliced into ~700-word contextual arrays.
3. System merges the context arrays into strict formatting prompts requiring LLM output to match embedded exact JSON structures.
4. Validation catches the response immediately, rejecting non-conformant JSON arrays or hallucinated structure headers.
5. Render passes validated dict array to Streamlit.
6. The user populates the answer dict.
7. Router logic evaluates inputs dynamically (Binary answers via Exact Match, One-word against Fuzz text, sentences sent directly back to the LLM mapped by grading Rubrics).
8. Values normalized across criteria weights output explicit total scores injected actively into local SQLite files, unlocking export capacities.

## 12. Failure Handling (Detailed)
The system prevents crashes by aggressively boxing component operations:
- **Ingestion Failures**: Malformed documents immediately flag UI warnings skipping payload processing while cleanly progressing the remaining viable batch components.
- **LLM Failures**: Wrapped with an explicit three-try feedback generator loop sending specific schema tracebacks. Excessive failures log to the terminal and output empty questions to prevent eternal looping.
- **UI Fallback**: Unsettled caching objects forcefully route users sequentially to the `app.py` welcome screen keeping core background files unharmed.

## 13. Known Edge Cases
- **Gigantic Files**: Uploads scaling rapidly over contextual bounds forcibly aggressively drop internal chunk sizes mathematically to map the Ollama hardware limits, potentially isolating key phrases.
- **Foreign Emoticons**: Export schemas forcibly sanitize or heavily constrain non-native control tags dynamically before printing to FPDF to prevent runtime collapsing.

## 14. Testing Framework
Maintain repository stability and assert logic handling using the mapped QA coverage offline:
```bash
pytest -q
```
*Note: `test_pipeline.py` executes strict deterministic testing independently by mocking the required complex JSON output dictionaries to eliminate native-LLM random discrepancies.*

## 15. Reproducibility Instructions
To exactly replicate the deployment states of your generation, delete the overarching `quiz_data.db` database entirely, delete dynamic `logs/` outputs globally, ensure `config.yaml` settings align with default commit footprints, and reboot sequence parameters cleanly in an isolated `.venv`. Ensure `ollama` natively has a pristine `llama3.2` container unpolluted by manual fine-tuning overrides.

## 16. Limitations
- **Hardware Bottlenecks**: Relies purely on host system GPU capacities allocating resources linearly. Memory constraints impact context loop depth directly.
- **Multimodal Constraints**: The current infrastructure treats images explicitly as base placeholders. Actual OCR/Computer Vision logic isn't bridged to the internal LLM natively.
- **Execution Wait times**: Synchronous LLM API calls severely delay large document batch productions.

## 17. Future Improvements
- Improvise native integration with smaller asynchronous worker pools managing LLM generation timeouts reactively.
- Implement explicit LLaMA 3.2 Vision multimodal context parsing on PDF graphical data.
- Refactor the FPDF output scaling bounds mathematically improving report layouts dynamically.

## 18. Project Structure
```text
src/
├── app.py             # Streamlit Route Entry
├── main.py            # Headless CLI Runner
├── config/            # Pydantic Settings & YAML defaults
├── chunking/          # Fingerprint-based document segmenting
├── evaluation/        # Orchestration layer for grading
├── grading/           # Heuristic and LLM-based comparators 
├── ingestion/         # Document parsers & multi-modality routers
├── question_generation/ # Distributed async-mimic builders
├── rubric_engine/     # Centralized criterion standardizer
├── storage/           # SQLite abstraction & session recovery
├── ui/                # Separated layout logic
└── validation/        # Content-gate schema testing
docs/
tests/
```

## 19. License
Distributed under the MIT License. See `LICENSE` for more information.
