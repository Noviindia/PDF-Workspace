import pytest
from app.core.table_detector import TableDetector

@pytest.fixture
def detector():
    return TableDetector()

def test_detect_tab_separated(detector):
    text = "Name\tAge\tCity\nJohn\t30\tNew York\nJane\t25\tLondon"
    tables = detector.detect_tables(text)
    assert len(tables) > 0
    assert tables[0].columns == ["Name", "Age", "City"]
    assert len(tables[0].rows) == 2

def test_detect_space_separated(detector):
    text = "Name       Age        City\nJohn       30         New York\nJane       25         London"
    tables = detector.detect_tables(text)
    assert len(tables) > 0
    assert "Name" in tables[0].columns

def test_detect_pipe_table(detector):
    text = "| Name | Age | City |\n|---|---|---|\n| John | 30 | New York |\n| Jane | 25 | London |"
    tables = detector.detect_tables(text)
    assert len(tables) > 0
    assert tables[0].columns == ["Name", "Age", "City"]
    assert len(tables[0].rows) == 2

def test_detect_aligned_columns(detector):
    text = "S.No  Student Name       Roll No\n1     Rahul Kumar        1041\n2     Amit Singh         1042"
    tables = detector.detect_tables(text)
    assert len(tables) > 0
    assert len(tables[0].columns) >= 3
    assert len(tables[0].rows) == 2

def test_no_table(detector):
    text = "This is just a regular paragraph of text.\nIt does not contain any table structure.\nJust some lines."
    tables = detector.detect_tables(text)
    assert len(tables) == 0

def test_header_detection(detector):
    text = "Name\tAge\tCity\nJohn\t30\tNew York\nJane\t25\tLondon"
    tables = detector.detect_tables(text)
    assert len(tables) > 0
    assert tables[0].columns == ["Name", "Age", "City"]
    assert ["John", "30", "New York"] in tables[0].rows
