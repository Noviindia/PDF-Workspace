import pytest
import os
import tempfile
from app.database.db_manager import DatabaseManager
from app.database.repository import Repository
from app.database.models import PageType, Record, Category
from app.core.search_engine import SearchEngine

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

@pytest.fixture
def search_engine(repo):
    return SearchEngine(repo)

def test_build_and_exact_search(search_engine, repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    repo.add_record(doc.id, 1, None, {"name": "Rahul Kumar", "class": "10"}, "Rahul Kumar Class 10", 0, 0, 0, 0)
    repo.add_record(doc.id, 2, None, {"name": "Amit Singh", "class": "10"}, "Amit Singh Class 10", 0, 0, 0, 0)
    
    search_engine.build_index(doc.id)
    
    results = search_engine.search("Rahul", doc.id)
    assert len(results) >= 1
    assert "Rahul" in results[0].text

def test_partial_search(search_engine, repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    repo.add_record(doc.id, 1, None, {"name": "Johnathan"}, "Johnathan Doe", 0, 0, 0, 0)
    search_engine.build_index(doc.id)
    
    results = search_engine.search("John*", doc.id)
    assert len(results) >= 1

def test_case_insensitive(search_engine, repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    repo.add_record(doc.id, 1, None, {"name": "JOHNATHAN"}, "JOHNATHAN", 0, 0, 0, 0)
    search_engine.build_index(doc.id)
    
    results = search_engine.search("johnathan", doc.id)
    assert len(results) >= 1

def test_multiple_results(search_engine, repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    repo.add_record(doc.id, 1, None, {"name": "Rahul Kumar"}, "Rahul Kumar 1", 0, 0, 0, 0)
    repo.add_record(doc.id, 2, None, {"name": "Rahul Singh"}, "Rahul Singh 2", 0, 0, 0, 0)
    repo.add_record(doc.id, 3, None, {"name": "Rahul Sharma"}, "Rahul Sharma 3", 0, 0, 0, 0)
    search_engine.build_index(doc.id)
    
    results = search_engine.search("Rahul", doc.id)
    assert len(results) == 3

def test_category_search(search_engine, repo):
    doc = repo.add_document("test.pdf", "/path/to/test.pdf", 10, PageType.NATIVE_TEXT, 1024)
    cat = repo.add_category(doc.id, "Class 10")
    repo.add_record(doc.id, 1, cat.id, {"name": "Rahul Kumar"}, "Rahul Kumar", 0, 0, 0, 0)
    repo.add_record(doc.id, 2, None, {"name": "Rahul Uncategorized"}, "Rahul Uncategorized", 0, 0, 0, 0)
    search_engine.build_index(doc.id)
    
    results = search_engine.search("Rahul", doc.id, category_id=cat.id)
    assert len(results) == 1

def test_single_character_hindi_search(search_engine, repo):
    """Test searching single character 'म' matches across entire document on multiple pages."""
    doc = repo.add_document("voters.pdf", "/path/to/voters.pdf", 10, PageType.NATIVE_TEXT, 2048)
    repo.add_record(doc.id, 1, None, {"name": "मनोज कुमार"}, "मनोज कुमार पुत्र राम प्रसाद", 10, 10, 100, 50)
    repo.add_record(doc.id, 2, None, {"name": "अमित शर्मा"}, "अमित शर्मा पुत्र श्याम शर्मा", 10, 10, 100, 50)
    repo.add_record(doc.id, 3, None, {"name": "सुरेश कुमार"}, "सुरेश कुमार पुत्र हरीश कुमार", 10, 10, 100, 50)
    repo.add_record(doc.id, 5, None, {"name": "मोहन लाल"}, "मोहन लाल पुत्र राम लाल", 10, 10, 100, 50)
    search_engine.build_index(doc.id)

    results = search_engine.search("म", doc.id)
    assert len(results) >= 3
    pages = [r.page_number for r in results]
    assert 1 in pages
    assert 2 in pages
    assert 5 in pages
    # Ensure ordered by page number
    assert pages == sorted(pages)

def test_hindi_prefix_search(search_engine, repo):
    """Test prefix search 'मानो' matches 'मनोज कुमार'."""
    doc = repo.add_document("voters.pdf", "/path/to/voters.pdf", 5, PageType.NATIVE_TEXT, 2048)
    repo.add_record(doc.id, 1, None, {"name": "मनोज कुमार"}, "मनोज कुमार पुत्र राम प्रसाद", 10, 10, 100, 50)
    search_engine.build_index(doc.id)

    results = search_engine.search("मानो", doc.id)
    assert len(results) >= 1
    assert any("मनोज" in r.text for r in results)

def test_hindi_spelling_variants_bidirectional(search_engine, repo):
    """Test 'मानोज' matches 'मनोज' and vice-versa."""
    doc = repo.add_document("voters.pdf", "/path/to/voters.pdf", 5, PageType.NATIVE_TEXT, 2048)
    repo.add_record(doc.id, 2, None, {"name": "मनोज कुमार"}, "मनोज कुमार", 20, 20, 120, 60)
    repo.add_record(doc.id, 4, None, {"name": "मानोज सिंह"}, "मानोज सिंह", 20, 20, 120, 60)
    search_engine.build_index(doc.id)

    # Searching 'मानोज' should find both
    results_a = search_engine.search("मानोज", doc.id)
    assert len(results_a) >= 2

    # Searching 'मनोज' should find both
    results_b = search_engine.search("मनोज", doc.id)
    assert len(results_b) >= 2

def test_whole_pdf_multi_page_search(search_engine, repo):
    """Test that search matches across all pages and returns sorted page results."""
    doc = repo.add_document("large.pdf", "/path/to/large.pdf", 20, PageType.NATIVE_TEXT, 4096)
    target_pages = [1, 3, 7, 12, 18]
    for p in target_pages:
        repo.add_record(doc.id, p, None, {"name": f"वोटर {p}"}, f"वोटर {p} ग्राम पंचायत", 0, 0, 0, 0)
    search_engine.build_index(doc.id)

    results = search_engine.search("वोटर", doc.id)
    assert len(results) == len(target_pages)
    assert [r.page_number for r in results] == target_pages

def test_bounding_box_record_fallback_highlight(repo):
    """Test finding bounding box on page when record bbox exists."""
    doc = repo.add_document("scanned.pdf", "/path/to/scanned.pdf", 5, PageType.SCANNED, 2048)
    p = repo.add_page(doc.id, 3, "", "मनोज कुमार", PageType.SCANNED, 95.0, 595, 842, False)
    repo.add_record(doc.id, 3, None, {"name": "मनोज कुमार"}, "मनोज कुमार", 50.0, 100.0, 200.0, 80.0)

    # Search with variant 'मानोज'
    boxes = repo.find_bounding_boxes_for_text(doc.id, 3, "मानोज")
    assert len(boxes) >= 1
    # Check coords (x0, y0, x1, y1) -> (50.0, 100.0, 250.0, 180.0)
    assert boxes[0] == (50.0, 100.0, 250.0, 180.0)


def test_boilerplate_suppression_single_char_search(search_engine, repo):
    """Test searching single char 'म' matches actual person data, NOT boilerplate labels (नाम, उम्र, मकान)."""
    doc = repo.add_document("voter_cards.pdf", "/path/to/voters.pdf", 2, PageType.NATIVE_TEXT, 2048)
    # Card 1: Manoj Kumar (has 'म' in name)
    repo.add_record(
        doc.id, 1, None,
        {"name": "मनोज कुमार", "relative_name": "राम प्रसाद", "voter_id": "ABC101", "house_no": "12"},
        "निर्वाचक का नाम : मनोज कुमार पिता का नाम : राम प्रसाद मकान संख्या : 12 उम्र : 32 लिंग : पुरुष",
        10, 10, 100, 50
    )
    # Card 2: Suresh Singh (NO 'म' in name or relative, only in template labels नाम, मकान, उम्र)
    repo.add_record(
        doc.id, 1, None,
        {"name": "सुरेश सिंह", "relative_name": "दिनेश सिंह", "voter_id": "ABC102", "house_no": "15"},
        "निर्वाचक का नाम : सुरेश सिंह पिता का नाम : दिनेश सिंह मकान संख्या : 15 उम्र : 45 लिंग : पुरुष",
        10, 70, 100, 50
    )
    search_engine.build_index(doc.id)

    # Searching 'म' must match Manoj Kumar, but NOT Suresh Singh
    results = search_engine.search("म", doc.id)
    assert len(results) == 1
    assert "मनोज कुमार" in results[0].text
    assert "सुरेश सिंह" not in [r.text for r in results]


def test_search_scopes(search_engine, repo):
    """Test searching with explicit scopes: Name, Voter ID, Exact Word."""
    doc = repo.add_document("scopes.pdf", "/path/to/scopes.pdf", 3, PageType.NATIVE_TEXT, 2048)
    repo.add_record(
        doc.id, 1, None,
        {"name": "मनोज कुमार", "relative_name": "सुरेश कुमार", "voter_id": "XYZ9999", "house_no": "10"},
        "मनोज कुमार XYZ9999",
        10, 10, 100, 50
    )
    search_engine.build_index(doc.id)

    # 1. Names Only scope
    res_name = search_engine.search("मनोज", doc.id, scope="Names Only (नाम)")
    assert len(res_name) == 1
    assert res_name[0].match_field.startswith("Name")

    res_id_in_name = search_engine.search("XYZ9999", doc.id, scope="Names Only (नाम)")
    assert len(res_id_in_name) == 0

    # 2. Voter ID scope
    res_id = search_engine.search("XYZ9999", doc.id, scope="Voter ID (EPIC)")
    assert len(res_id) == 1
    assert res_id[0].match_field.startswith("Voter ID")

    res_name_in_id = search_engine.search("मनोज", doc.id, scope="Voter ID (EPIC)")
    assert len(res_name_in_id) == 0

    # 3. Exact Word scope
    res_exact = search_engine.search("मनोज", doc.id, scope="Exact Word (सटीक)")
    assert len(res_exact) == 1


def test_clean_structured_snippet_formatting(search_engine, repo):
    """Test that search snippet is cleanly formatted with icons and bold highlights."""
    doc = repo.add_document("snippets.pdf", "/path/to/snippets.pdf", 1, PageType.NATIVE_TEXT, 1024)
    repo.add_record(
        doc.id, 1, None,
        {"name": "मनोज कुमार", "relative_name": "राम प्रसाद", "voter_id": "EPIC1234", "house_no": "42"},
        "निर्वाचक का नाम : मनोज कुमार पिता का नाम : राम प्रसाद मकान संख्या : 42",
        10, 10, 100, 50
    )
    search_engine.build_index(doc.id)

    results = search_engine.search("मनोज", doc.id)
    assert len(results) == 1
    snippet = results[0].context_snippet
    assert "👤" in snippet
    assert "<b>मनोज</b>" in snippet
    assert "EPIC1234" in snippet


def test_hindi_nasal_and_pancham_akshar_matching(search_engine, repo):
    """Test bidirectional matching between anusvara and half-nasals (e.g. राजेंद्र <-> राजेन्द्र, आनंद <-> आनन्द)."""
    doc = repo.add_document("voters_nasal.pdf", "/path/to/voters.pdf", 2, PageType.NATIVE_TEXT, 2048)
    # Stored with half-nasal 'राजेन्द्र'
    repo.add_record(doc.id, 1, None, {"name": "राजेन्द्र प्रसाद", "relation_name": "आनन्द प्रसाद"}, "राजेन्द्र प्रसाद", 0, 0, 0, 0)
    # Stored with anusvara 'राजेंद्र'
    repo.add_record(doc.id, 2, None, {"name": "राजेंद्र सिंह", "relation_name": "सुरेन्द्र सिंह"}, "राजेंद्र सिंह", 0, 0, 0, 0)
    search_engine.build_index(doc.id)

    # 1. Search with anusvara 'राजेंद्र' -> must find BOTH
    res_anusvara = search_engine.search("राजेंद्र", doc.id)
    assert len(res_anusvara) == 2

    # 2. Search with pancham akshar 'राजेन्द्र' -> must find BOTH
    res_pancham = search_engine.search("राजेन्द्र", doc.id)
    assert len(res_pancham) == 2

    # 3. Search relation name 'आनंद' -> matches 'आनन्द प्रसाद'
    res_anand = search_engine.search("आनंद", doc.id)
    assert len(res_anand) >= 1
    assert "आनन्द" in res_anand[0].context_snippet


def test_hindi_dropped_anusvara_tolerance(search_engine, repo):
    """Test OCR dropped anusvara tolerance (सिंह <-> सिह)."""
    doc = repo.add_document("voters_singh.pdf", "/path/to/voters.pdf", 1, PageType.NATIVE_TEXT, 1024)
    # Stored as 'सिह' (OCR dropped dot)
    repo.add_record(doc.id, 1, None, {"name": "अमर सिह"}, "अमर सिह", 0, 0, 0, 0)
    # Stored as 'सिंह'
    repo.add_record(doc.id, 1, None, {"name": "विक्रम सिंह"}, "विक्रम सिंह", 0, 0, 0, 0)
    search_engine.build_index(doc.id)

    # Searching 'सिंह' finds both 'सिह' and 'सिंह'
    results = search_engine.search("सिंह", doc.id)
    assert len(results) == 2

    # Searching 'सिह' also finds both
    results_sih = search_engine.search("सिह", doc.id)
    assert len(results_sih) == 2


def test_arabic_and_devanagari_numeral_interchange(search_engine, repo):
    """Test searching numbers matches both Arabic (12, 35) and Devanagari (१२, ३५) numerals."""
    doc = repo.add_document("voters_num.pdf", "/path/to/voters.pdf", 1, PageType.NATIVE_TEXT, 1024)
    repo.add_record(
        doc.id, 1, None,
        {"name": "राकेश कुमार", "house_no": "१२", "age": "३५", "serial_no": "५"},
        "राकेश कुमार मकान १२ उम्र ३५",
        10, 10, 100, 50
    )
    search_engine.build_index(doc.id)

    # 1. Search with Arabic '12' -> matches house_no '१२'
    res_12 = search_engine.search("12", doc.id)
    assert len(res_12) == 1

    # 2. Search with Devanagari '१२' -> matches
    res_dev12 = search_engine.search("१२", doc.id)
    assert len(res_dev12) == 1

    # 3. Search with Arabic '35' -> matches age '३५'
    res_35 = search_engine.search("35", doc.id)
    assert len(res_35) == 1


def test_zero_width_joiner_tolerance(search_engine, repo):
    """Test that text with invisible ZWJ/ZWNJ font ligatures matches user queries cleanly."""
    doc = repo.add_document("zwj.pdf", "/path/to/zwj.pdf", 1, PageType.NATIVE_TEXT, 1024)
    # Document contains ZWJ in 'प्र\u200dसाद'
    repo.add_record(
        doc.id, 1, None,
        {"name": "राम प्र\u200dसाद", "relation_name": "शिव प्र\u200dसाद"},
        "राम प्र\u200dसाद",
        10, 10, 100, 50
    )
    search_engine.build_index(doc.id)

    # Searching clean 'प्रसाद' without ZWJ matches
    results = search_engine.search("प्रसाद", doc.id)
    assert len(results) == 1
    assert "प्रसाद" in results[0].context_snippet


def test_all_record_fields_and_list_search(search_engine, repo):
    """Test searching gender (महिला, पुरुष), relation_name, and custom list fields."""
    doc = repo.add_document("list.pdf", "/path/to/list.pdf", 1, PageType.NATIVE_TEXT, 1024)
    repo.add_record(
        doc.id, 1, None,
        {"name": "सुनीता देवी", "relation_name": "सुरेश कुमार", "gender": "महिला", "village": "बाज़िदपुर"},
        "सुनीता देवी सुरेश कुमार महिला बाज़िदपुर",
        10, 10, 100, 50
    )
    repo.add_record(
        doc.id, 1, None,
        {"name": "अमित कुमार", "relation_name": "सुरेश कुमार", "gender": "पुरुष", "village": "रामपुर"},
        "अमित कुमार सुरेश कुमार पुरुष रामपुर",
        10, 60, 100, 50
    )
    search_engine.build_index(doc.id)

    # 1. Search 'महिला' -> returns Sunita Devi
    res_female = search_engine.search("महिला", doc.id)
    assert len(res_female) == 1
    assert "सुनीता" in res_female[0].text or "सुनीता" in res_female[0].context_snippet

    # 2. Search father's name 'सुरेश कुमार' via relation_name -> returns both
    res_rel = search_engine.search("सुरेश", doc.id)
    assert len(res_rel) == 2

    # 3. Search custom field 'बाज़िदपुर' -> returns Sunita Devi with village match
    res_village = search_engine.search("बाज़िदपुर", doc.id)
    assert len(res_village) == 1

    # 4. Phonetic variant 'वाज़िदपुर' matches 'बाज़िदपुर'
    res_v_village = search_engine.search("वाज़िदपुर", doc.id)
    assert len(res_v_village) == 1


def test_bounding_box_normalized_highlight(repo):
    """Test that word bounding boxes with ZWJ or Devanagari numerals are retrieved correctly."""
    doc = repo.add_document("bbox_zwj.pdf", "/path/to/bbox.pdf", 1, PageType.NATIVE_TEXT, 1024)
    p = repo.add_page(doc.id, 1, "प्र\u200dसाद", "प्र\u200dसाद", PageType.NATIVE_TEXT, 99.0, 595, 842, False)
    repo.add_bounding_box(p.id, "प्र\u200dसाद", 10.0, 20.0, 80.0, 40.0, "word")

    # Search for clean 'प्रसाद'
    boxes = repo.find_bounding_boxes_for_text(doc.id, 1, "प्रसाद")
    assert len(boxes) >= 1
    assert boxes[0] == (10.0, 20.0, 80.0, 40.0)


def test_hindi_single_words_from_list(search_engine, repo):
    """Test that single words from list entries (names, surnames, castes, relations, villages) are detected with precision."""
    doc = repo.add_document("pacs_roster.pdf", "/path/to/roster.pdf", 3, PageType.NATIVE_TEXT, 4096)
    # Roster card 1: Rajendra Singh
    repo.add_record(
        doc.id, 1, None,
        {
            "serial_no": "1",
            "voter_id": "EPIC1001",
            "name": "राजेन्द्र सिंह",
            "relation_name": "रामेश्वर सिंह",
            "relation_type": "पिता",
            "house_no": "14",
            "age": "48",
            "gender": "पुरुष",
            "village": "बाज़िदपुर",
            "designation": "अध्यक्ष"
        },
        "क्र० सं० : 1 पहचान पत्र : EPIC1001 नाम : राजेन्द्र सिंह पिता का नाम : रामेश्वर सिंह मकान : 14 उम्र : 48 लिंग : पुरुष ग्राम : बाज़िदपुर पद : अध्यक्ष",
        10, 10, 200, 80
    )
    # Roster card 2: Shanti Devi
    repo.add_record(
        doc.id, 2, None,
        {
            "serial_no": "2",
            "voter_id": "EPIC1002",
            "name": "शान्ति देवी",
            "relation_name": "राजेन्द्र सिंह",
            "relation_type": "पति",
            "house_no": "14",
            "age": "45",
            "gender": "महिला",
            "village": "बाज़िदपुर",
            "designation": "सदस्य"
        },
        "क्र० सं० : 2 पहचान पत्र : EPIC1002 नाम : शान्ति देवी पति का नाम : राजेन्द्र सिंह मकान : 14 उम्र : 45 लिंग : महिला ग्राम : बाज़िदपुर पद : सदस्य",
        10, 10, 200, 80
    )
    # Roster card 3: Govind Prasad
    repo.add_record(
        doc.id, 3, None,
        {
            "serial_no": "3",
            "voter_id": "EPIC1003",
            "name": "गोविन्द प्रसाद",
            "relation_name": "हरि प्रसाद",
            "relation_type": "पिता",
            "house_no": "22",
            "age": "32",
            "gender": "पुरुष",
            "village": "रामपुर",
            "designation": "सचिव"
        },
        "क्र० सं० : 3 पहचान पत्र : EPIC1003 नाम : गोविन्द प्रसाद पिता का नाम : हरि प्रसाद मकान : 22 उम्र : 32 लिंग : पुरुष ग्राम : रामपुर पद : सचिव",
        10, 10, 200, 80
    )
    search_engine.build_index(doc.id)

    # 1. Single word first name 'राजेंद्र' (anusvara) -> finds Card 1 and Card 2 (where Rajendra is relation)
    r1 = search_engine.search("राजेंद्र", doc.id)
    assert len(r1) == 2

    # 2. Single word surname 'सिंह' -> finds Card 1 and Card 2
    r2 = search_engine.search("सिंह", doc.id)
    assert len(r2) == 2

    # 3. Single word 'सिह' (OCR dropped dot) -> finds Card 1 and Card 2
    r3 = search_engine.search("सिह", doc.id)
    assert len(r3) == 2

    # 4. Single word 'शांति' (anusvara) -> finds 'शान्ति देवी' on Page 2
    r4 = search_engine.search("शांति", doc.id)
    assert len(r4) == 1
    assert r4[0].page_number == 2

    # 5. Single word 'देवी' -> finds Card 2
    r5 = search_engine.search("देवी", doc.id)
    assert len(r5) == 1
    assert r5[0].page_number == 2

    # 6. Single word 'गोविंद' (anusvara) -> finds 'गोविन्द प्रसाद' on Page 3
    r6 = search_engine.search("गोविंद", doc.id)
    assert len(r6) == 1
    assert r6[0].page_number == 3

    # 7. Single word 'प्रसाद' -> finds Card 3
    r7 = search_engine.search("प्रसाद", doc.id)
    assert len(r7) == 1
    assert r7[0].page_number == 3

    # 8. Single word 'महिला' -> finds Card 2
    r8 = search_engine.search("महिला", doc.id)
    assert len(r8) == 1
    assert r8[0].page_number == 2

    # 9. Single word 'पुरुष' -> finds Card 1 and Card 3
    r9 = search_engine.search("पुरुष", doc.id)
    assert len(r9) == 2

    # 10. Single word 'अध्यक्ष' (designation) -> finds Card 1
    r10 = search_engine.search("अध्यक्ष", doc.id)
    assert len(r10) == 1
    assert r10[0].page_number == 1

    # 11. Single word 'सचिव' (designation) -> finds Card 3
    r11 = search_engine.search("सचिव", doc.id)
    assert len(r11) == 1
    assert r11[0].page_number == 3

    # 12. Single word 'बाज़िदपुर' (village) -> finds Card 1 and Card 2
    r12 = search_engine.search("बाज़िदपुर", doc.id)
    assert len(r12) == 2



