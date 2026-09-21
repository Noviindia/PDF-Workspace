import os
import json
import zipfile
import tempfile
import pytest
from app.services.project_service import ProjectService
from app.services.processing_service import ProcessingService
from app.services.export_service import ExportService
from app.database.models import ExportConfig


@pytest.fixture
def sample_pdf_path():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_students.pdf")
    assert os.path.exists(path), f"Fixture not found at {path}"
    return path


def test_full_pdf_workspace_pipeline(sample_pdf_path):
    """
    Complete end-to-end verification of:
    1. Project creation
    2. PDF import & page extraction
    3. Table detection & structured record extraction
    4. Automatic category detection & assignment
    5. Full-text search (SQLite FTS5) on pages and structured data
    6. Record editing & OCR correction tracking
    7. Multi-format export across scopes (XLSX, DOCX, CSV, JSON, HTML, TXT, MD)
    8. Project persistence & reload from project.db
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = os.path.join(tmpdir, "student_workspace")
        project_svc = ProjectService()
        
        # 1. Create Project
        proc_svc = project_svc.create_project(project_dir, "Student Workspace")
        assert os.path.exists(os.path.join(project_dir, "project.db"))
        assert os.path.exists(os.path.join(project_dir, "source"))
        assert os.path.exists(os.path.join(project_dir, "exports"))
        
        # 2. Import & Analyze PDF
        doc_id = proc_svc.import_pdf(sample_pdf_path)
        assert doc_id > 0
        
        repo = proc_svc.get_repository()
        
        # Check Document
        doc = repo.get_document(doc_id)
        assert doc is not None
        assert doc.page_count == 10
        assert doc.file_size > 0
        
        # Check Pages
        pages = repo.get_pages_by_document(doc_id)
        assert len(pages) == 10
        for p in pages:
            assert len(p.raw_text.strip()) > 0
            assert p.width > 0
            assert p.height > 0
            
        # 3. Tables & Records
        tables = repo.get_tables_by_document(doc_id)
        assert len(tables) >= 5
        records = repo.get_all_records(doc_id)
        assert len(records) >= 50
        
        # 4. Categories
        categories = repo.get_categories(doc_id)
        category_names = [c.name for c in categories]
        assert any("Class 10" in name for name in category_names)
        assert any("Class 9" in name for name in category_names)
        
        # 5. Search Engine & FTS5
        search_engine = proc_svc.get_search_engine()
        search_results = search_engine.search("Rahul", doc_id=doc_id)
        assert len(search_results) >= 3
        result_pages = {r.page_number for r in search_results}
        assert 2 in result_pages
        
        # Search records
        rec_matches = repo.search_records("Rahul", doc_id=doc_id)
        assert len(rec_matches) >= 2
        
        # 6. Record Editing & OCR Correction
        target_rec = rec_matches[0]
        original_name = target_rec.data.get("Name", "")
        corrected_name = original_name + " (Verified)"
        
        # Add correction audit trail
        corr = repo.add_correction(
            record_id=target_rec.id,
            field_name="Name",
            original_value=original_name,
            corrected_value=corrected_name
        )
        assert corr is not None
        assert corr.original_value == original_name
        assert corr.corrected_value == corrected_name
        
        # Update record in DB
        new_data = dict(target_rec.data)
        new_data["Name"] = corrected_name
        repo.update_record(target_rec.id, data=new_data, is_edited=1)
        
        # Verify persistence of record update & corrections
        updated_rec = repo.get_record(target_rec.id)
        assert updated_rec.data["Name"] == corrected_name
        assert updated_rec.is_edited == 1
        corrections = repo.get_corrections_by_record(target_rec.id)
        assert len(corrections) == 1
        assert corrections[0].corrected_value == corrected_name
        
        # 7. Multi-Format Export across Scopes
        export_svc = ExportService(repo)
        formats = ["xlsx", "docx", "csv", "json", "html", "txt", "md"]
        
        # Scope: ALL
        for fmt in formats:
            out_file = os.path.join(project_dir, "exports", f"export_all.{fmt}")
            cfg = ExportConfig(
                format=fmt,
                scope="all",
                category_id=None,
                record_ids=None,
                search_query=None,
                output_path=out_file
            )
            res = export_svc.export(cfg)
            assert os.path.exists(res)
            size = os.path.getsize(res)
            assert size > 0, f"{fmt} file was empty"
            
            # Detailed validation per format
            if fmt == "json":
                with open(res, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    assert isinstance(data, list) or "records" in data
            elif fmt == "csv":
                with open(res, "r", encoding="utf-8") as cf:
                    content = cf.read()
                    assert "Name" in content
            elif fmt == "html":
                with open(res, "r", encoding="utf-8") as hf:
                    content = hf.read()
                    assert "<html" in content.lower()
                    assert "<table" in content.lower()
            elif fmt == "md":
                with open(res, "r", encoding="utf-8") as mf:
                    content = mf.read()
                    assert "#" in content
                    assert "|" in content
            elif fmt == "txt":
                with open(res, "r", encoding="utf-8") as tf:
                    content = tf.read()
                    assert len(content) > 100
            elif fmt in ("xlsx", "docx"):
                with zipfile.ZipFile(res, "r") as zf:
                    namelist = zf.namelist()
                    if fmt == "xlsx":
                        assert any("workbook.xml" in n for n in namelist)
                    elif fmt == "docx":
                        assert any("document.xml" in n for n in namelist)
                        
        # Scope: CATEGORY
        cat_with_recs = next((c for c in categories if c.record_count > 0), categories[0])
        out_cat = os.path.join(project_dir, "exports", "category_export.csv")
        export_svc.export(ExportConfig(
            format="csv",
            scope="category",
            category_id=cat_with_recs.id,
            record_ids=None,
            search_query=None,
            output_path=out_cat
        ))
        assert os.path.exists(out_cat)
        assert os.path.getsize(out_cat) > 0
        
        # Scope: SELECTED
        selected_ids = [records[0].id, records[1].id, records[2].id]
        out_sel = os.path.join(project_dir, "exports", "selected_export.json")
        export_svc.export(ExportConfig(
            format="json",
            scope="selected",
            category_id=None,
            record_ids=selected_ids,
            search_query=None,
            output_path=out_sel
        ))
        assert os.path.exists(out_sel)
        with open(out_sel, "r", encoding="utf-8") as f:
            sel_data = json.load(f)
            assert len(sel_data) == 3
            
        # Scope: SEARCH
        out_search = os.path.join(project_dir, "exports", "search_export.html")
        export_svc.export(ExportConfig(
            format="html",
            scope="search",
            category_id=None,
            record_ids=None,
            search_query="Rahul",
            output_path=out_search
        ))
        assert os.path.exists(out_search)
        assert os.path.getsize(out_search) > 0
        
        proc_svc.close()
        
        # 8. Persistence & Reload Project
        assert project_svc.is_valid_project(project_dir)
        reopened_svc = project_svc.open_project(project_dir)
        reopened_repo = reopened_svc.get_repository()
        
        docs = reopened_repo.get_all_documents()
        assert len(docs) == 1
        assert docs[0].name == os.path.basename(sample_pdf_path)
        
        reopened_records = reopened_repo.get_all_records(doc_id)
        assert len(reopened_records) == len(records)
        
        # Verify the edited record remained updated after reload
        reloaded_target = reopened_repo.get_record(target_rec.id)
        assert reloaded_target.data["Name"] == corrected_name
        assert reloaded_target.is_edited == 1
        
        reopened_corrections = reopened_repo.get_corrections_by_record(target_rec.id)
        assert len(reopened_corrections) == 1
        assert reopened_corrections[0].original_value == original_name
        assert reopened_corrections[0].corrected_value == corrected_name
        
        reopened_svc.close()
