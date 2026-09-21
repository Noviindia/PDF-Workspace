import os
import io
import tempfile
import pytest
from PIL import Image, ImageDraw, ImageFont
import fitz

from app.web.server import create_app


@pytest.fixture
def sample_test_pdf():
    """Generates a small test PDF with text for web API tests."""
    fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)

    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    page.insert_text((50, 50), "Student Examination Report")
    page.insert_text((50, 100), "Name: Ramesh Kumar")
    page.insert_text((50, 150), "Father Name: Mohan Lal")
    page.insert_text((50, 200), "Roll No: 12345")
    page.insert_text((50, 250), "Result: Pass Grade A")
    doc.save(pdf_path)
    doc.close()

    yield pdf_path

    if os.path.exists(pdf_path):
        os.unlink(pdf_path)


@pytest.fixture
def web_client(tmp_path):
    """Creates a Flask test client with an isolated temporary data directory."""
    app = create_app(data_dir=str(tmp_path))
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_web_index(web_client):
    """Verify that the home route renders the single-page application HTML."""
    res = web_client.get('/')
    assert res.status_code == 200
    assert b"PDF Workspace Online" in res.data
    assert b"Google Lens" in res.data


def test_web_api_status(web_client):
    """Verify that the status API returns system status and OCR availability."""
    res = web_client.get('/api/status')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'online'
    assert 'lens_available' in data
    assert 'total_pages' in data


def test_web_upload_and_pipeline(web_client, sample_test_pdf):
    """Verify PDF upload, document metadata, image render, search, and export."""
    with open(sample_test_pdf, 'rb') as f:
        pdf_bytes = f.read()

    # 1. Upload PDF
    data = {
        'file': (io.BytesIO(pdf_bytes), 'sample_student.pdf'),
        'ocr_engine': 'auto',
        'ocr_language': 'eng+hin',
        'layout_mode': 'auto',
        'force_ocr': 'false'
    }
    upload_res = web_client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert upload_res.status_code == 200
    upload_json = upload_res.get_json()
    assert upload_json['success'] is True
    doc_id = upload_json['doc_id']
    assert doc_id > 0

    # 2. Get Document Details
    doc_res = web_client.get(f'/api/documents/{doc_id}')
    assert doc_res.status_code == 200
    doc_json = doc_res.get_json()
    assert doc_json['total_pages'] == 1
    assert doc_json['filename'] == 'sample_student.pdf'

    # 3. Render Page Image
    img_res = web_client.get(f'/api/documents/{doc_id}/pages/1/image?dpi=72')
    assert img_res.status_code == 200
    assert img_res.content_type == 'image/png'
    # PNG signature check
    assert img_res.data[:8] == b'\x89PNG\r\n\x1a\n'

    # 4. Search in Document
    search_res = web_client.get(f'/api/documents/{doc_id}/search?q=Ramesh')
    assert search_res.status_code == 200
    search_json = search_res.get_json()
    assert search_json['total_matches'] >= 1
    assert any(r['page_number'] == 1 for r in search_json['results'])

    # 5. Search Highlights
    hl_res = web_client.get(f'/api/documents/{doc_id}/pages/1/highlights?q=Ramesh')
    assert hl_res.status_code == 200
    hl_json = hl_res.get_json()
    assert 'boxes' in hl_json
    assert hl_json['page_width'] > 0
    assert hl_json['page_height'] > 0

    # 6. Page Raw Text
    txt_res = web_client.get(f'/api/documents/{doc_id}/pages/1/text')
    assert txt_res.status_code == 200
    txt_json = txt_res.get_json()
    assert 'Ramesh' in (txt_json.get('raw_text') or txt_json.get('processed_text'))

    # 7. Export XLSX
    export_res = web_client.get(f'/api/documents/{doc_id}/export/xlsx')
    assert export_res.status_code == 200
    assert 'attachment' in export_res.headers.get('Content-Disposition', '')
    assert len(export_res.data) > 0

    # 8. Export CSV
    csv_res = web_client.get(f'/api/documents/{doc_id}/export/csv')
    assert csv_res.status_code == 200
    assert 'attachment' in csv_res.headers.get('Content-Disposition', '')
    assert len(csv_res.data) > 0

    # 9. Export DOCX
    docx_res = web_client.get(f'/api/documents/{doc_id}/export/docx')
    assert docx_res.status_code == 200
    assert 'attachment' in docx_res.headers.get('Content-Disposition', '')

    # 10. Structured Records Listing
    rec_res = web_client.get(f'/api/documents/{doc_id}/records')
    assert rec_res.status_code == 200
    rec_json = rec_res.get_json()
    assert 'records' in rec_json
    assert 'columns' in rec_json

    # 11. Invalid export format error
    bad_res = web_client.get(f'/api/documents/{doc_id}/export/invalid_fmt')
    assert bad_res.status_code == 400


def test_web_document_not_found(web_client):
    """Verify 404 response for nonexistent document."""
    res = web_client.get('/api/documents/99999')
    assert res.status_code == 404

