import pytest
from src.validation.validator import validate_content

def test_pipeline_validation_gate():
    # Simulate first pipeline step
    text = "Valid testing text with enough words to bypass the word count limits imposed by the content validator. We need at least something around 20 words or so. Let's add a few more to be safe. " * 3
    ok, msg = validate_content(text)
    assert ok is True
