import os
import tempfile
import pytest
from PIL import Image, ImageDraw, ImageFont
import fitz

from app.core.ocr_engine import OCREngine, get_tessdata_dir
from app.services.processing_service import ProcessingService


@pytest.fixture(scope="module")
def scanned_hindi_eng_pdf():
    """Generates a realistic scanned/image PDF containing both English and Hindi text."""
    fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)

    img = Image.new("RGB", (900, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    font_path = "/System/Library/Fonts/Kohinoor.ttc"
    if not os.path.exists(font_path):
        font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"

    try:
        font = ImageFont.truetype(font_path, 32)
    except Exception:
        font = ImageFont.load_default()

    draw.text((40, 40), "Student Certificate", fill=(0, 0, 0), font=font)
    draw.text((40, 110), "Candidate Name: Ramesh Kumar", fill=(0, 0, 0), font=font)
    draw.text((40, 180), "हिंदी परीक्षा परिणाम: उत्तीर्ण", fill=(0, 0, 0), font=font)
    draw.text((40, 250), "Roll Number: 98765", fill=(0, 0, 0), font=font)
    draw.text((40, 320), "Grade: A+ Distinction", fill=(0, 0, 0), font=font)

    temp_img = tempfile.mktemp(suffix=".png")
    img.save(temp_img)

    doc = fitz.open()
    page = doc.new_page(width=900, height=400)
    page.insert_image(fitz.Rect(0, 0, 900, 400), filename=temp_img)
    doc.save(pdf_path)
    doc.close()

    if os.path.exists(temp_img):
        os.unlink(temp_img)

    yield pdf_path

    if os.path.exists(pdf_path):
        os.unlink(pdf_path)


def test_tessdata_presence():
    """Verify that bundled English and Hindi traineddata are detected."""
    tessdata = get_tessdata_dir()
    assert tessdata is not None
    assert os.path.exists(os.path.join(tessdata, "eng.traineddata"))
    assert os.path.exists(os.path.join(tessdata, "hin.traineddata"))


def test_ocr_engine_hindi_english(scanned_hindi_eng_pdf):
    """Verify OCREngine extracts English and Hindi text with bounding boxes."""
    engine = OCREngine()
    assert engine.is_available()

    # Bilingual OCR
    res = engine.ocr_page_from_file(scanned_hindi_eng_pdf, 0, language="eng+hin")
    assert res is not None
    assert len(res.text.strip()) > 0
    assert "Ramesh" in res.text or "Kumar" in res.text or "98765" in res.text
    assert len(res.blocks) >= 3

    # Check bounding box coordinates are non-zero
    first_block = res.blocks[0]
    assert first_block.x1 > first_block.x0
    assert first_block.y1 > first_block.y0


def test_pipeline_scanned_pdf_search_and_highlight(scanned_hindi_eng_pdf):
    """Verify that importing an image PDF indexes text into FTS5 and enables search highlighting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ps = ProcessingService(tmpdir)
        doc_id = ps.import_pdf(scanned_hindi_eng_pdf, ocr_language="eng+hin")
        assert doc_id > 0

        repo = ps.get_repository()
        pages = repo.get_pages_by_document(doc_id)
        assert len(pages) == 1

        # Text should have been populated via OCR
        page_text = pages[0].raw_text or pages[0].processed_text
        assert len(page_text.strip()) > 0

        # Search for English keyword in image PDF
        search_engine = ps.get_search_engine()
        results_en = search_engine.search("Ramesh", document_id=doc_id)
        assert len(results_en) >= 1
        assert any(1 == r.page_number for r in results_en)

        # Search for number
        results_num = search_engine.search("98765", document_id=doc_id)
        assert len(results_num) >= 1

        # Verify bounding box lookup returns coordinates for visual highlighting
        boxes = repo.find_bounding_boxes_for_text(doc_id, 1, "Ramesh")
        assert len(boxes) >= 1
        x0, y0, x1, y1 = boxes[0]
        assert x1 > x0
        assert y1 > y0

        ps.close()


def test_google_lens_availability_and_fallback(scanned_hindi_eng_pdf):
    """Verify Google Lens OCR availability and graceful fallback when offline/error."""
    from unittest.mock import patch

    engine = OCREngine()
    assert engine._check_lens() is True

    # Test explicit tesseract engine
    res_tess = engine.ocr_page_from_file(scanned_hindi_eng_pdf, 0, language="eng+hin", engine_type="tesseract")
    assert res_tess is not None
    assert len(res_tess.text.strip()) > 0

    # Test lens fallback to tesseract when lens encounters an exception (e.g. offline)
    with patch.object(engine, '_ocr_lens', side_effect=RuntimeError("Lens Network Timeout")):
        res_fallback = engine.ocr_page_from_file(scanned_hindi_eng_pdf, 0, language="eng+hin", engine_type="lens")
        assert res_fallback is not None
        # Fallback should succeed using local backend
        assert len(res_fallback.text.strip()) > 0

