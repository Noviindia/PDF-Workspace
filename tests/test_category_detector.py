import pytest
from app.core.category_detector import CategoryDetector
from app.database.models import Category

@pytest.fixture
def detector():
    return CategoryDetector()

def test_detect_class_pattern(detector):
    text = "Some intro text.\nClass 10\nHere is the data."
    categories = detector.detect_categories(text)
    assert any(c.name == "Class 10" for c in categories)

def test_detect_section_pattern(detector):
    text = "Class 10 - Section A\nData goes here."
    categories = detector.detect_categories(text)
    names = [c.name for c in categories]
    assert any("Section A" in n or "Class 10" in n for n in names)

def test_detect_from_headings(detector):
    # Depending on implementation, it might extract anything that looks like a heading
    text = "Summary Report\n\nTotal Students by Class\n\nGender Distribution"
    categories = detector.detect_categories(text)
    names = [c.name for c in categories]
    # It might detect 'Summary Report' or 'Total Students by Class'
    assert len(categories) > 0

def test_no_categories(detector):
    text = "Just some normal text without any clear headings or class mentions."
    categories = detector.detect_categories(text)
    assert len(categories) == 0

def test_multiple_categories(detector):
    text = "Class 10 Section A\nSome data\nClass 10 Section B\nMore data"
    categories = detector.detect_categories(text)
    assert len(categories) >= 2
