import pytest
import os
import tempfile
import sqlite3
from app.database.db_manager import DatabaseManager
from app.database.repository import Repository
from app.database.models import PageType, Document, Page, Record, Category

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    yield path
    os.close(fd)
    if os.path.exists(path):
        os.unlink(path)

@pytest.fixture
def repo(temp_db):
    db_manager = DatabaseManager(temp_db)
    db_manager.initialize()
    return Repository(db_manager)

def test_create_database(temp_db):
    db_manager = DatabaseManager(temp_db)
    db_manager.initialize()
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    assert "documents" in tables
    assert "pages" in tables
    assert "records" in tables
    assert "categories" in tables
    assert "project_meta" in tables
    assert "search_index" in tables
    conn.close()

def test_add_document(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    assert doc is not None
    assert doc.name == "test.pdf"
    assert doc.page_count == 10
    
    fetched = repo.get_document(doc.id)
    assert fetched is not None
    assert fetched.name == "test.pdf"

def test_add_page(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    page = repo.add_page(
        document_id=doc.id,
        page_number=1,
        raw_text="Sample raw text",
        processed_text="Sample raw text",
        page_type=PageType.NATIVE_TEXT,
        ocr_confidence=None,
        width=612.0,
        height=792.0,
        has_tables=False
    )
    assert page is not None
    assert page.page_number == 1
    assert "Sample" in page.raw_text

def test_add_record(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    rec = repo.add_record(
        document_id=doc.id,
        page_number=1,
        category_id=None,
        data={"name": "Rahul Kumar", "roll_no": "1041"},
        source_text="1 Rahul Kumar 1041",
        bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0
    )
    assert rec is not None
    assert rec.data["name"] == "Rahul Kumar"
    assert rec.source_page == 1

def test_update_record(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    rec = repo.add_record(
        document_id=doc.id,
        page_number=1,
        category_id=None,
        data={"name": "RahuI Kumar", "roll_no": "1041"},
        source_text="1 RahuI Kumar 1041",
        bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0
    )
    repo.update_record(rec.id, data={"name": "Rahul Kumar", "roll_no": "1041"}, is_edited=1)
    
    updated = repo.get_record(rec.id)
    assert updated.data["name"] == "Rahul Kumar"
    assert updated.is_edited is True

def test_delete_record(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    rec = repo.add_record(
        document_id=doc.id,
        page_number=1,
        category_id=None,
        data={"name": "John Doe"},
        source_text="John Doe",
        bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0
    )
    assert repo.get_record(rec.id) is not None
    repo.delete_record(rec.id)
    assert repo.get_record(rec.id) is None

def test_add_category(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    cat = repo.add_category(document_id=doc.id, name="Class 10")
    assert cat is not None
    assert cat.name == "Class 10"

def test_update_category_counts(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    cat = repo.add_category(document_id=doc.id, name="Class 10")
    
    repo.add_record(doc.id, 1, cat.id, {"name": "Student 1"}, "Student 1", 0, 0, 0, 0)
    repo.add_record(doc.id, 1, cat.id, {"name": "Student 2"}, "Student 2", 0, 0, 0, 0)
    repo.update_category_counts(doc.id)
    
    cat_updated = repo.get_category(cat.id)
    assert cat_updated.record_count == 2

def test_merge_categories(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    cat1 = repo.add_category(doc.id, "Class 10 A")
    cat2 = repo.add_category(doc.id, "Class 10 B")
    
    repo.add_record(doc.id, 1, cat1.id, {"name": "Rahul"}, "Rahul", 0, 0, 0, 0)
    repo.add_record(doc.id, 1, cat2.id, {"name": "Amit"}, "Amit", 0, 0, 0, 0)
    
    repo.merge_categories([cat2.id], cat1.id)
    repo.update_category_counts(doc.id)
    
    recs_in_cat1 = repo.get_records_by_category(cat1.id)
    assert len(recs_in_cat1) == 2

def test_search_index_and_queries(repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    repo.add_page(doc.id, 1, "Rahul Kumar Class 10 student", "Rahul Kumar Class 10 student", PageType.NATIVE_TEXT, None, 612, 792, False)
    rec = repo.add_record(doc.id, 1, None, {"name": "Rahul Kumar", "roll_no": "1041"}, "Rahul Kumar 1041", 0, 0, 0, 0)
    repo.rebuild_search_index(doc.id)
    
    # Exact search
    results = repo.search("Rahul", doc.id)
    assert len(results) > 0
    assert any("Rahul" in r.text for r in results)
    
    # Prefix search
    results_prefix = repo.search("Rah*", doc.id)
    assert len(results_prefix) > 0

def test_project_meta(repo):
    repo.set_meta("project_name", "Local PDF Test")
    assert repo.get_meta("project_name") == "Local PDF Test"
