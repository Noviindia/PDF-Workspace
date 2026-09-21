import pytest
from app.core.record_extractor import RecordExtractor, ExtractedRecord

@pytest.fixture
def extractor():
    return RecordExtractor()

def test_voter_list_detection(extractor):
    hindi_text = 'निर्वाचक नामावली 2024 S04 बिहार विधानसभा निर्वाचन क्षेत्र का विवरण'
    assert extractor.is_voter_list_content(hindi_text) is True

    pacs_text = 'बाज़िदपुर पैक्स मतदाता सूची 2023 प्राथमिक कृषि साख समिति'
    assert extractor.is_voter_list_content(pacs_text) is True

    normal_text = 'Annual Financial Report 2024 for Samastipur Bank'
    assert extractor.is_voter_list_content(normal_text) is False

def test_sequential_hindi_voter_cards(extractor):
    text = """
1 ABC1234567
निर्वाचक का नाम : राम कुमार
पिता का नाम : मोहन लाल
मकान संख्या : 12
उम्र : 45  लिंग : पुरुष
फोटो उपलब्ध है

2 ABC1234568
निर्वाचक का नाम : श्याम सिंह
पिता का नाम : सोहन सिंह
मकान संख्या : 14
उम्र : 32  लिंग : पुरुष
फोटो उपलब्ध है

3 XYZ9876543
निर्वाचक का नाम : गीता देवी
पति का नाम : राम कुमार
मकान संख्या : 12
उम्र : 40  लिंग : महिला
फोटो उपलब्ध है
"""
    records = extractor.extract_voter_cards(text, page_number=1)
    assert len(records) == 3
    
    # Voter 1
    r1 = records[0].data
    assert r1['serial_no'] == '1'
    assert r1['voter_id'] == 'ABC1234567'
    assert r1['name'] == 'राम कुमार'
    assert r1['relation_name'] == 'मोहन लाल'
    assert r1['relation_type'] == 'पिता'
    assert r1['house_no'] == '12'
    assert r1['age'] == '45'
    assert r1['gender'] == 'पुरुष'
    assert records[0].page_number == 1

    # Voter 2
    r2 = records[1].data
    assert r2['serial_no'] == '2'
    assert r2['voter_id'] == 'ABC1234568'
    assert r2['name'] == 'श्याम सिंह'
    assert r2['age'] == '32'
    assert r2['gender'] == 'पुरुष'

    # Voter 3
    r3 = records[2].data
    assert r3['serial_no'] == '3'
    assert r3['voter_id'] == 'XYZ9876543'
    assert r3['name'] == 'गीता देवी'
    assert r3['relation_name'] == 'राम कुमार'
    assert r3['relation_type'] == 'पति'
    assert r3['gender'] == 'महिला'

def test_horizontal_matrix_card_decomposition(extractor):
    text = """
1 ABC1234567               2 ABC1234568               3 XYZ9876543
निर्वाचक का नाम : राम कुमार    निर्वाचक का नाम : श्याम सिंह    निर्वाचक का नाम : गीता देवी
पिता का नाम : मोहन लाल       पिता का नाम : सोहन सिंह       पति का नाम : राम कुमार
मकान संख्या : 12            मकान संख्या : 14            मकान संख्या : 12
उम्र : 45  लिंग : पुरुष       उम्र : 32  लिंग : पुरुष       उम्र : 40  लिंग : महिला
"""
    records = extractor.extract_voter_cards(text, page_number=2)
    assert len(records) == 3
    names = [r.data['name'] for r in records]
    assert 'राम कुमार' in names
    assert 'श्याम सिंह' in names
    assert 'गीता देवी' in names
    assert all(r.page_number == 2 for r in records)

def test_spatial_block_clustering(extractor):
    from dataclasses import dataclass
    @dataclass
    class MockBlock:
        text: str
        x0: float
        y0: float
        x1: float
        y1: float

    # 3 columns across page (W=600)
    blocks = [
        # Col 1
        MockBlock("1 BR01001001\nनिर्वाचक का नाम : अमित कुमार\nपिता का नाम : सुरेश कुमार\nमकान संख्या : 1\nउम्र : 28 लिंग : पुरुष", 20, 100, 180, 200),
        # Col 2
        MockBlock("2 BR01001002\nनिर्वाचक का नाम : पूजा कुमारी\nपति का नाम : अमित कुमार\nमकान संख्या : 1\nउम्र : 25 लिंग : महिला", 220, 100, 380, 200),
        # Col 3
        MockBlock("3 BR01001003\nनिर्वाचक का नाम : राजेश कुमार\nपिता का नाम : रमेश कुमार\nमकान संख्या : 2\nउम्र : 50 लिंग : पुरुष", 420, 100, 580, 200),
    ]

    records = extractor.extract_voter_cards('', page_number=3, blocks=blocks)
    assert len(records) == 3
    assert records[0].data['name'] == 'अमित कुमार'
    assert records[1].data['name'] == 'पूजा कुमारी'
    assert records[2].data['name'] == 'राजेश कुमार'
