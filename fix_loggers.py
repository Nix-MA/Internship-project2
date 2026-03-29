import re

files_to_fix = [
    "c:/Users/ASUS/Downloads/quiz-doc-ai-v2/src/validation/validator.py",
    "c:/Users/ASUS/Downloads/quiz-doc-ai-v2/src/question_generation/generator.py",
    "c:/Users/ASUS/Downloads/quiz-doc-ai-v2/src/grading/llm_grader.py",
    "c:/Users/ASUS/Downloads/quiz-doc-ai-v2/src/ingestion/extractor.py",
    "c:/Users/ASUS/Downloads/quiz-doc-ai-v2/src/evaluation/evaluator.py",
    "c:/Users/ASUS/Downloads/quiz-doc-ai-v2/src/chunking/chunker.py"
]

for fp in files_to_fix:
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Replace imports
    content = re.sub(r'from src\.utils\.logger import.*', r'from src.utils.logger import get_logger', content)
    content = re.sub(r'from utils\.logger import.*', r'from src.utils.logger import get_logger', content)
    
    # 2. Replace log_error calls
    content = re.sub(r'log_error\(([^,]+),\s*(.*?)\)', r'\1.error(\2)', content)

    # 3. Replace logger instances
    content = content.replace("ingestion_logger", "get_logger('ingestion')")
    content = content.replace("llm_logger", "get_logger('llm')")
    content = content.replace("error_logger", "get_logger('error')")
    
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)

print("Logging fixed.")
