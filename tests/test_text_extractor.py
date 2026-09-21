import pytest
import os
from app.core.text_extractor import TextExtractor

def test_extract_text():
    pdf_path = "tests/fixtures/sample_students.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("Sample PDF not found")
        
    extractor = TextExtractor(pdf_path)
    text = extractor.extract_text(0)
    assert text is not None

def test_page_count():
    pdf_path = "tests/fixtures/sample_students.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("Sample PDF not found")
        
    extractor = TextExtractor(pdf_path)
    count = extractor.get_page_count()
    assert count > 0

def test_page_dimensions():
    pdf_path = "tests/fixtures/sample_students.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("Sample PDF not found")
        
    extractor = TextExtractor(pdf_path)
    width, height = extractor.get_page_dimensions(0)
    assert width > 0
    assert height > 0

def test_has_text():
    pdf_path = "tests/fixtures/sample_students.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("Sample PDF not found")
        
    extractor = TextExtractor(pdf_path)
    text = extractor.extract_text(0)
    assert len(text.strip()) > 0

def test_extract_blocks():
    pdf_path = "tests/fixtures/sample_students.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("Sample PDF not found")
        
    extractor = TextExtractor(pdf_path)
    blocks = extractor.extract_blocks(0)
    assert isinstance(blocks, list)
