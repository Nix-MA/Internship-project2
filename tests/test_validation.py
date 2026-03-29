import pytest
from src.chunking.chunker import is_valid_chunk, _CONTENT_REJECTION_PATTERNS
from src.validation.validator import validate_content

def test_xlsx_sheet_padding_rejection():
    # If the chunk is almost entirely [Sheet: Summary] repeating, it should be rejected.
    sheet_chunk = '[Sheet: Summary] [Sheet: Data] [Sheet: Overview] ' * 5
    assert is_valid_chunk(sheet_chunk) is False, "Highly repetitive non-alpha chunk should fall below alpha ratio threshold"

def test_hardcoded_error_patterns_rejected():
    # Specifically "install llama model" text from vision errors
    error_chunk = 'Note install llama model for this image file because the vision feature requires additional setup'
    assert is_valid_chunk(error_chunk) is False, "LLM instruction errors should be rejected"
    
def test_extraction_error_patterns_rejected():
    error_chunk2 = '[Extraction error for report.pdf: unable to parse] and some extra words here to exceed MIN_WORDS threshold'
    assert is_valid_chunk(error_chunk2) is False, "Literal extraction error flags should be rejected"

def test_whitespace_content_validation():
    ok, msg = validate_content("   \n\t  \n  ")
    assert ok is False, "Whitespace-only document should not be valid"
    assert "Insufficient text content" in msg
