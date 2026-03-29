import argparse
import sys
import json
from pathlib import Path

# Setup path so running from anywhere works
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.extractor import extract_document
from src.chunking.chunker import chunk_text
from src.validation.validator import validate_content
from src.question_generation import generate_questions_distributed
from src.utils.logger import get_logger

logger = get_logger("cli")

def run_pipeline(file_path: str, q_type: str, count: int, marks: int):
    logger.info(f"Starting CLI pipeline for: {file_path}")
    
    # 1. Extraction
    doc = extract_document(file_path)
    content = doc.get("content", "")
    if not content:
        logger.error("Failed to extract text or file is empty.")
        sys.exit(1)
        
    # 2. Validation
    ok, msg = validate_content(content)
    if not ok:
        logger.error(f"Validation failed: {msg}")
        sys.exit(1)
        
    # 3. Chunking
    chunks = chunk_text(content)
    if not chunks:
        logger.error("No valid chunks produced.")
        sys.exit(1)
        
    # 4. Generation
    logger.info(f"Generating {count} {q_type} questions...")
    try:
        questions = generate_questions_distributed(chunks, q_type, count, marks)
        
        # 5. Output
        print("\n=== GENERATION RESULTS ===")
        print(json.dumps(questions, indent=2))
        print("==========================\n")
        logger.info("Pipeline completed successfully.")
        
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lumina Assessment Offline CLI")
    parser.add_argument("file", help="Path to the input document (PDF, TXT, DOCX, etc.)")
    parser.add_argument("--type", default="MCQ", help="Question type to generate")
    parser.add_argument("--count", type=int, default=3, help="Number of questions to generate")
    parser.add_argument("--marks", type=int, default=1, help="Marks per question")
    args = parser.parse_args()
    
    run_pipeline(args.file, args.type, args.count, args.marks)
