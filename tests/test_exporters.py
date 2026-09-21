import pytest
import os
import json
import csv
import tempfile
from app.database.db_manager import DatabaseManager
from app.database.repository import Repository
from app.database.models import PageType, Record, Category, ExportConfig
from app.exporters.xlsx_exporter import XLSXExporter
from app.exporters.docx_exporter import DOCXExporter
from app.exporters.csv_exporter import CSVExporter
from app.exporters.json_exporter import JSONExporter
from app.exporters.html_exporter import HTMLExporter
from app.exporters.txt_exporter import TXTExporter
from app.exporters.markdown_exporter import MarkdownExporter

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    yield path
    os.close(fd)
    if os.path.exists(path):
        os.unlink(path)

@pytest.fixture
def repo_with_data(temp_db):
    db_manager = DatabaseManager(temp_db)
    db_manager.initialize()
    repo = Repository(db_manager)
    
    doc = repo.add_document("students.pdf", "/path/to/students.pdf", 5, PageType.NATIVE_TEXT, 2048)
    cat1 = repo.add_category(doc.id, "Class 10")
    cat2 = repo.add_category(doc.id, "Class 9")
    
    r1 = repo.add_record(doc.id, 1, cat1.id, {"name": "Rahul Kumar", "roll_no": "1041", "gender": "Male"}, "Rahul Kumar 1041", 0, 0, 0, 0)
    r2 = repo.add_record(doc.id, 1, cat1.id, {"name": "Neha Kumari", "roll_no": "1042", "gender": "Female"}, "Neha Kumari 1042", 0, 0, 0, 0)
    r3 = repo.add_record(doc.id, 2, cat2.id, {"name": "Rahul Sharma", "roll_no": "2031", "gender": "Male"}, "Rahul Sharma 2031", 0, 0, 0, 0)
    repo.update_category_counts(doc.id)
    repo.rebuild_search_index(doc.id)
    return repo, doc, cat1, cat2, [r1, r2, r3]

def test_xlsx_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "export.xlsx")
    exporter = XLSXExporter(repo)
    config = ExportConfig(format="xlsx", scope="all", category_id=None, record_ids=None, search_query=None, output_path=out_file)
    exporter.export(config)
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 100

def test_docx_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "export.docx")
    exporter = DOCXExporter(repo)
    config = ExportConfig(format="docx", scope="all", category_id=None, record_ids=None, search_query=None, output_path=out_file)
    exporter.export(config)
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 100

def test_csv_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "export.csv")
    exporter = CSVExporter(repo)
    config = ExportConfig(format="csv", scope="all", category_id=None, record_ids=None, search_query=None, output_path=out_file)
    exporter.export(config)
    assert os.path.exists(out_file)
    with open(out_file, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        assert "Rahul Kumar" in content
        assert "Neha Kumari" in content

def test_json_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "export.json")
    exporter = JSONExporter(repo)
    config = ExportConfig(format="json", scope="all", category_id=None, record_ids=None, search_query=None, output_path=out_file)
    exporter.export(config)
    assert os.path.exists(out_file)
    with open(out_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert len(data["records"]) == 3
        assert data["document"]["name"] == "All Records"

def test_html_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "export.html")
    exporter = HTMLExporter(repo)
    config = ExportConfig(format="html", scope="all", category_id=None, record_ids=None, search_query=None, output_path=out_file)
    exporter.export(config)
    assert os.path.exists(out_file)
    with open(out_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "<html>" in content.lower() or "<!doctype html>" in content.lower()
        assert "Rahul Kumar" in content

def test_markdown_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "export.md")
    exporter = MarkdownExporter(repo)
    config = ExportConfig(format="markdown", scope="all", category_id=None, record_ids=None, search_query=None, output_path=out_file)
    exporter.export(config)
    assert os.path.exists(out_file)
    with open(out_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "# All Records" in content
        assert "Rahul Kumar" in content

def test_txt_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "export.txt")
    exporter = TXTExporter(repo)
    config = ExportConfig(format="txt", scope="all", category_id=None, record_ids=None, search_query=None, output_path=out_file)
    exporter.export(config)
    assert os.path.exists(out_file)
    with open(out_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "Rahul Kumar" in content

def test_scope_category_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "cat1.csv")
    exporter = CSVExporter(repo)
    config = ExportConfig(format="csv", scope="category", category_id=cat1.id, record_ids=None, search_query=None, output_path=out_file)
    exporter.export(config)
    with open(out_file, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        assert "Rahul Kumar" in content
        assert "Neha Kumari" in content
        assert "Rahul Sharma" not in content

def test_scope_search_export(repo_with_data, tmp_path):
    repo, doc, cat1, cat2, records = repo_with_data
    out_file = str(tmp_path / "search.csv")
    exporter = CSVExporter(repo)
    config = ExportConfig(format="csv", scope="search", category_id=None, record_ids=None, search_query="Sharma", output_path=out_file)
    exporter.export(config)
    with open(out_file, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        assert "Rahul Sharma" in content
        assert "Neha Kumari" not in content
