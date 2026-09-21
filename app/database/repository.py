import re
import json
import unicodedata
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from app.database.db_manager import DatabaseManager
from app.database.models import (
    PageType, Document, Page, Record, Category,
    BoundingBox, SearchResult, UserCorrection, ProjectMeta, TableData
)

DEVANAGARI_DIGITS = '०१२३४५६७८९'
ARABIC_DIGITS = '0123456789'
DEV_TO_ARABIC = str.maketrans(DEVANAGARI_DIGITS, ARABIC_DIGITS)
ARABIC_TO_DEV = str.maketrans(ARABIC_DIGITS, DEVANAGARI_DIGITS)
DEVANAGARI_CONSONANTS = set('कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहक़ख़ग़ज़ड़ढ़फ़')

NASAL_PAIRS = [
    ('न्द्र', 'ंद्र'),
    ('न्द', 'ंद'),
    ('न्त', 'ंत'),
    ('न्थ', 'ंथ'),
    ('न्ध', 'ंध'),
    ('न्श', 'ंश'),
    ('न्स', 'ंस'),
    ('म्ब', 'ंब'),
    ('म्प', 'ंप'),
    ('ण्ड', 'ंड'),
    ('ण्ठ', 'ंठ'),
    ('ञ्ज', 'ंज'),
    ('ञ्च', 'ंच'),
    ('ङ्क', 'ंक'),
    ('ङ्ग', 'ंग'),
]


def normalize_devanagari(text: str) -> str:
    """Normalizes Devanagari text:
    - Normalizes Unicode to NFC form
    - Removes zero-width joiner (\\u200d), ZWNJ (\\u200c), BOM (\\ufeff), and zero-width spaces (\\u200b, \\u200e, \\u200f)
    - Normalizes Hindi dandas (।, ॥)
    - Collapses repeated whitespace
    """
    if not text:
        return ""
    res = unicodedata.normalize('NFC', str(text))
    for ch in ('\u200c', '\u200d', '\ufeff', '\u200b', '\u200e', '\u200f'):
        res = res.replace(ch, '')
    res = res.replace('।', ' ').replace('॥', ' ')
    return re.sub(r'\s+', ' ', res).strip()


def get_hindi_search_variants(query: str) -> List[str]:
    """Generate normalized search variants for Hindi/Devanagari text.
    Handles:
    - Zero-width character stripping and NFC normalization
    - Devanagari <-> Arabic numeral conversion (e.g. 12 <-> १२)
    - Nasal / Anusvara vs Pancham Akshar (e.g. राजेंद्र <-> राजेन्द्र, शांति <-> शान्ति, आनंद <-> आनन्द)
    - Dropped Anusvara in OCR (e.g. सिंह <-> सिह, कुँवर <-> कुंवर <-> कुवर)
    - Nukta normalization (ज़ <-> ज, फ़ <-> फ, ड़ <-> ड, ढ़ <-> ढ)
    - Vowel 'ा' (aa matra) variations (मानोज <-> मनोज)
    - Matra swaps (ि <-> ी, ु <-> ू)
    - Consonant swaps (व <-> ब, श <-> ष <-> स, ण <-> न)
    """
    clean = normalize_devanagari(query)
    if not clean:
        return []
    variants = [clean]

    # 1. Numeral conversion (Arabic <-> Devanagari)
    if any(ch in DEVANAGARI_DIGITS for ch in clean):
        v = clean.translate(DEV_TO_ARABIC)
        if v not in variants:
            variants.append(v)
    if any(ch in ARABIC_DIGITS for ch in clean):
        v = clean.translate(ARABIC_TO_DEV)
        if v not in variants:
            variants.append(v)

    # Check if text contains Devanagari characters (\u0900 - \u097F)
    has_devanagari = any('\u0900' <= ch <= '\u097F' for ch in clean)
    if not has_devanagari:
        return variants

    # 2. Nukta normalization (\u093c)
    if '\u093c' in clean:
        no_nukta = clean.replace('\u093c', '')
        if no_nukta not in variants:
            variants.append(no_nukta)
    else:
        for base, nuk in [('ज', 'ज़'), ('फ', 'फ़'), ('ड', 'ड़'), ('ढ', 'ढ़')]:
            if base in clean:
                v = clean.replace(base, nuk)
                if v not in variants:
                    variants.append(v)

    # 3. Nasal / Anusvara ('ं') vs Pancham Akshar (half-nasals)
    for half_nasal, anusvara in NASAL_PAIRS:
        if half_nasal in clean:
            v = clean.replace(half_nasal, anusvara)
            if v not in variants:
                variants.append(v)
            break
    for half_nasal, anusvara in NASAL_PAIRS:
        if anusvara in clean:
            v = clean.replace(anusvara, half_nasal)
            if v not in variants:
                variants.append(v)
            break

    # 4. Dropped Anusvara in OCR (e.g. सिंह <-> सिह)
    if '\u0902' in clean:
        no_dot = clean.replace('\u0902', '')
        if no_dot not in variants:
            variants.append(no_dot)
    elif 'सिह' in clean:
        with_dot = clean.replace('सिह', 'सिंह')
        if with_dot not in variants:
            variants.append(with_dot)

    # 5. Swap Anusvara 'ं' (\u0902) and Chandrabindu 'ँ' (\u0901)
    if '\u0902' in clean:
        v = clean.replace('\u0902', '\u0901')
        if v not in variants:
            variants.append(v)
    elif '\u0901' in clean:
        v = clean.replace('\u0901', '\u0902')
        if v not in variants:
            variants.append(v)
        no_cb = clean.replace('\u0901', '')
        if no_cb not in variants:
            variants.append(no_cb)

    # 6. Vowel 'ा' (aa matra) variations on consonants
    if '\u093e' in clean:
        no_first_aa = clean.replace('\u093e', '', 1)
        if no_first_aa not in variants:
            variants.append(no_first_aa)
        no_all_aa = clean.replace('\u093e', '')
        if no_all_aa not in variants:
            variants.append(no_all_aa)
    elif len(clean) >= 2 and clean[0] in DEVANAGARI_CONSONANTS:
        with_aa = clean[0] + '\u093e' + clean[1:]
        if with_aa not in variants:
            variants.append(with_aa)

    # 7. Swap i / ii matras (ि \u093f and ी \u0940)
    if '\u093f' in clean:
        v = clean.replace('\u093f', '\u0940')
        if v not in variants:
            variants.append(v)
    elif '\u0940' in clean:
        v = clean.replace('\u0940', '\u093f')
        if v not in variants:
            variants.append(v)

    # 8. Swap u / uu matras (ु \u0941 and ू \u0942)
    if '\u0941' in clean:
        v = clean.replace('\u0941', '\u0942')
        if v not in variants:
            variants.append(v)
    elif '\u0942' in clean:
        v = clean.replace('\u0942', '\u0941')
        if v not in variants:
            variants.append(v)

    # 9. Swap व <-> ब
    if 'व' in clean:
        v = clean.replace('व', 'ब')
        if v not in variants:
            variants.append(v)
    elif 'ब' in clean:
        v = clean.replace('ब', 'व')
        if v not in variants:
            variants.append(v)

    # 10. Sibilant exchange (श <-> ष <-> स)
    if 'श' in clean:
        for target in ('स', 'ष'):
            v = clean.replace('श', target)
            if v not in variants:
                variants.append(v)
    elif 'ष' in clean:
        for target in ('स', 'श'):
            v = clean.replace('ष', target)
            if v not in variants:
                variants.append(v)
    elif 'स' in clean:
        for target in ('श', 'ष'):
            v = clean.replace('स', target)
            if v not in variants:
                variants.append(v)

    # 11. ण <-> न
    if 'ण' in clean:
        v = clean.replace('ण', 'न')
        if v not in variants:
            variants.append(v)
    elif 'न' in clean:
        v = clean.replace('न', 'ण')
        if v not in variants:
            variants.append(v)

    return list(dict.fromkeys(variants))


BOILERPLATE_PATTERNS = [
    re.compile(r'निर्वाचक\s*(?:का)?\s*नाम\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'पिता\s*(?:का)?\s*नाम\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'पति\s*(?:का)?\s*नाम\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'माता\s*(?:का)?\s*नाम\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'अन्य\s*(?:का)?\s*नाम\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'संबंधी\s*(?:का)?\s*नाम\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'मकान\s*संख्या\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'गृह\s*संख्या\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'उम्र\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'आयु\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'लिंग\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'पहचान\s*पत्र\s*(?:क्रमांक)?\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'अनुभाग\s*संख्या\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'विधान\s*सभा\s*(?:निर्वाचन)?\s*(?:क्षेत्र)?\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'भाग\s*संख्या\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'क्रम\s*संख्या\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'ग्राम\s*पंचायत\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'वार्ड\s*संख्या\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'मतदान\s*स्थल\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'फोटो\s*उपलब्ध\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'हस्ताक्षर\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'Elector\'?s?\s*Name\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'Father\'?s?\s*Name\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'Husband\'?s?\s*Name\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'House\s*No\.?\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'Age\s*[:\-\.]?', re.IGNORECASE),
    re.compile(r'Gender\s*[:\-\.]?', re.IGNORECASE),
]


def strip_boilerplate_labels(text: str) -> str:
    """Removes voter card template labels and boilerplate headers from text."""
    if not text:
        return ""
    res = text
    for pat in BOILERPLATE_PATTERNS:
        res = pat.sub(" ", res)
    return re.sub(r'\s+', ' ', res).strip()


def clean_devanagari(text: str) -> str:
    """Normalizes Devanagari text by removing zero-width characters and normalizing punctuation."""
    return normalize_devanagari(text)


def highlight_snippet_term(text: str, term: str) -> str:
    """Wraps occurrences of term in <b>...</b>, case-insensitively and Devanagari-normalized."""
    if not text or not term:
        return text or ""
    clean_text = normalize_devanagari(text)
    clean_term = normalize_devanagari(term)
    pos = clean_text.lower().find(clean_term.lower())
    matched_len = len(clean_term)
    if pos == -1:
        variants = get_hindi_search_variants(clean_term)
        for v in variants:
            pos = clean_text.lower().find(v.lower())
            if pos != -1:
                matched_len = len(v)
                break
    if pos == -1:
        pos = text.lower().find(term.lower())
        if pos != -1:
            return f"{text[:pos]}<b>{text[pos:pos+len(term)]}</b>{text[pos+len(term):]}"
        return text
    return f"{clean_text[:pos]}<b>{clean_text[pos:pos+matched_len]}</b>{clean_text[pos+matched_len:]}"


def _make_snippet(text: str, match_term: str, window: int = 40) -> str:
    """Generate a clean context snippet highlighting match_term with <b>...</b> tags."""
    if not text:
        return ""
    pos = text.lower().find(match_term.lower())
    if pos == -1:
        clean_text = text.replace('\n', ' ').strip()
        return clean_text[:100] + ("..." if len(clean_text) > 100 else "")
    start = max(0, pos - window)
    end = min(len(text), pos + len(match_term) + window)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    snippet_body = (
        text[start:pos] +
        f"<b>{text[pos:pos+len(match_term)]}</b>" +
        text[pos+len(match_term):end]
    ).replace('\n', ' ')
    return prefix + snippet_body + suffix


def format_record_snippet(rec: Record, matched_term: str) -> str:
    """Creates a clean, structured snippet for a record with highlighted match."""
    data = rec.data or {}
    name = str(data.get('name', '') or '').strip()
    rel_type = str(data.get('relation_type', 'पिता') or 'पिता').strip()
    rel_name = str(data.get('relation_name', '') or data.get('relative_name', '') or '').strip()
    house_no = str(data.get('house_no', '') or '').strip()
    voter_id = str(data.get('voter_id', '') or data.get('epic_no', '') or '').strip()
    age = str(data.get('age', '') or '').strip()
    gender = str(data.get('gender', '') or '').strip()
    
    parts = []
    if name:
        parts.append(f"👤 {highlight_snippet_term(name, matched_term)}")
    if rel_name:
        parts.append(f"{rel_type}: {highlight_snippet_term(rel_name, matched_term)}")
    if house_no:
        parts.append(f"मकान: {highlight_snippet_term(house_no, matched_term)}")
    if age:
        parts.append(f"उम्र: {highlight_snippet_term(age, matched_term)}")
    if gender:
        parts.append(f"लिंग: {highlight_snippet_term(gender, matched_term)}")
    if voter_id:
        parts.append(f"EPIC: {highlight_snippet_term(voter_id, matched_term)}")

    # Include matching custom fields (e.g. village, caste, table columns)
    standard_keys = {'name', 'relative_name', 'relation_name', 'relation_type', 'house_no', 'voter_id', 'epic_no', 'age', 'gender'}
    norm_variants = [v.lower() for v in get_hindi_search_variants(matched_term)]
    for k, v in data.items():
        if k not in standard_keys and v:
            v_str = str(v).strip()
            norm_v = normalize_devanagari(v_str).lower()
            if any(var in norm_v for var in norm_variants):
                label = k.replace('_', ' ').title()
                parts.append(f"{label}: {highlight_snippet_term(v_str, matched_term)}")

    if parts:
        return "  •  ".join(parts)
    
    clean = strip_boilerplate_labels(rec.source_text or "")
    return _make_snippet(clean or rec.source_text or "", matched_term)


def score_record_match(rec: Record, clean_q: str, variants: List[str], scope: str = 'all') -> Tuple[float, str, str, str]:
    """
    Evaluates a record against query and variants according to scope.
    Returns: (score, match_field, matched_term, snippet)
    score == 0.0 means no match.
    """
    scope_norm = scope.lower().strip()
    if 'name' in scope_norm or 'नाम' in scope_norm:
        scope_key = 'name'
    elif 'voter' in scope_norm or 'epic' in scope_norm or 'id' in scope_norm or 'पहचान' in scope_norm:
        scope_key = 'voter_id'
    elif 'exact' in scope_norm or 'सटीक' in scope_norm:
        scope_key = 'exact'
    else:
        scope_key = 'all'

    score = 0.0
    match_field = ""
    matched_term = clean_q
    data = rec.data or {}

    name = normalize_devanagari(str(data.get('name', '') or '').strip())
    rel_name = normalize_devanagari(str(data.get('relation_name', '') or data.get('relative_name', '') or '').strip())
    voter_id = str(data.get('voter_id', '') or data.get('epic_no', '') or '').strip()
    house_no = normalize_devanagari(str(data.get('house_no', '') or '').strip())
    source_raw = normalize_devanagari(rec.source_text or '')
    clean_source = strip_boilerplate_labels(source_raw)

    norm_variants = [normalize_devanagari(v) for v in variants if v]

    # 1. Voter ID scope
    if scope_key == 'voter_id':
        if voter_id:
            for v in norm_variants:
                if not v:
                    continue
                if v.lower() == voter_id.lower():
                    return (1000.0, "Voter ID (सटीक EPIC)", v, format_record_snippet(rec, v))
                elif v.lower() in voter_id.lower():
                    return (800.0, "Voter ID (EPIC)", v, format_record_snippet(rec, v))
        return (0.0, "", "", "")

    # 2. Exact word scope
    if scope_key == 'exact':
        for v in norm_variants:
            if not v:
                continue
            v_esc = re.escape(v)
            boundary_pattern = re.compile(r'(?:\b|^|\s)' + v_esc + r'(?:\b|$|\s)', re.IGNORECASE)
            if name and boundary_pattern.search(name):
                return (950.0, "Name (सटीक शब्द)", v, format_record_snippet(rec, v))
            if voter_id and boundary_pattern.search(voter_id):
                return (850.0, "Voter ID (सटीक EPIC)", v, format_record_snippet(rec, v))
            if rel_name and boundary_pattern.search(rel_name):
                return (750.0, "Relative (सटीक शब्द)", v, format_record_snippet(rec, v))
            for k, val in data.items():
                if k not in ('name', 'voter_id', 'epic_no', 'relation_name', 'relative_name'):
                    val_clean = normalize_devanagari(str(val or ''))
                    if val_clean and boundary_pattern.search(val_clean):
                        return (700.0, f"{k.replace('_', ' ').title()} (सटीक शब्द)", v, format_record_snippet(rec, v))
            if clean_source and boundary_pattern.search(clean_source):
                return (600.0, "Exact Word (सटीक शब्द)", v, format_record_snippet(rec, v))
        return (0.0, "", "", "")

    # 3. Check Name (if scope is 'all' or 'name')
    if name:
        name_words = name.split()
        for v in norm_variants:
            if not v:
                continue
            if name.lower() == v.lower():
                if score < 1000.0:
                    score, match_field, matched_term = 1000.0, "Name (नाम सटीक)", v
            elif any(w.lower() == v.lower() for w in name_words):
                if score < 900.0:
                    score, match_field, matched_term = 900.0, "Name (नाम शब्द)", v
            elif name.lower().startswith(v.lower()):
                if score < 850.0:
                    score, match_field, matched_term = 850.0, "Name (नाम शुरुआत)", v
            elif v.lower() in name.lower():
                if score < 700.0:
                    score, match_field, matched_term = 700.0, "Name (नाम अंश)", v

    # 4. Check Relative Name (if scope is 'all' or 'name')
    if rel_name and (scope_key in ('all', 'name')):
        rel_words = rel_name.split()
        for v in norm_variants:
            if not v:
                continue
            if rel_name.lower() == v.lower() or any(w.lower() == v.lower() for w in rel_words):
                if score < 650.0:
                    score, match_field, matched_term = 650.0, "Relative (संबंधी शब्द)", v
            elif rel_name.lower().startswith(v.lower()):
                if score < 600.0:
                    score, match_field, matched_term = 600.0, "Relative (संबंधी शुरुआत)", v
            elif v.lower() in rel_name.lower():
                if score < 500.0:
                    score, match_field, matched_term = 500.0, "Relative (संबंधी)", v

    # If scope was 'name', return name/relative match or nothing
    if scope_key == 'name':
        if score > 0.0:
            return (score, match_field, matched_term, format_record_snippet(rec, matched_term))
        return (0.0, "", "", "")

    # 5. Check Voter ID (for scope 'all')
    if voter_id:
        for v in norm_variants:
            if not v:
                continue
            if v.lower() == voter_id.lower():
                if score < 950.0:
                    score, match_field, matched_term = 950.0, "Voter ID (सटीक EPIC)", v
            elif v.lower() in voter_id.lower():
                if score < 750.0:
                    score, match_field, matched_term = 750.0, "Voter ID (EPIC)", v

    # 6. Check House No (supports Arabic <-> Devanagari numerals)
    if house_no:
        for v in norm_variants:
            if not v:
                continue
            if house_no.lower() == v.lower():
                if score < 600.0:
                    score, match_field, matched_term = 600.0, "House No (मकान सटीक)", v
            elif v.lower() in house_no.lower():
                if score < 400.0:
                    score, match_field, matched_term = 400.0, "House No (मकान)", v

    # 7. Check ALL other fields in rec.data (e.g. gender, age, village, serial_no, table columns)
    checked_keys = {'name', 'relative_name', 'relation_name', 'relation_type', 'voter_id', 'epic_no', 'house_no'}
    for k, val in data.items():
        if k in checked_keys or val is None:
            continue
        val_clean = normalize_devanagari(str(val).strip())
        if not val_clean:
            continue
        val_words = val_clean.split()
        for v in norm_variants:
            if not v:
                continue
            lbl = k.replace('_', ' ').title()
            if val_clean.lower() == v.lower():
                if score < 650.0:
                    score, match_field, matched_term = 650.0, f"{lbl} ({val_clean})", v
            elif any(w.lower() == v.lower() for w in val_words):
                if score < 600.0:
                    score, match_field, matched_term = 600.0, f"{lbl} ({v})", v
            elif v.lower() in val_clean.lower():
                if score < 500.0:
                    score, match_field, matched_term = 500.0, f"{lbl} ({val_clean})", v

    # 8. Check clean_source / source_raw (with boilerplate suppression)
    if score == 0.0:
        for v in norm_variants:
            if not v:
                continue
            # For short queries (<= 3 chars, e.g. 'म'), require clean_source match (NOT boilerplate!)
            if len(clean_q) <= 3:
                if v.lower() in clean_source.lower():
                    score, match_field, matched_term = 250.0, "Content (विवरण)", v
                    break
            else:
                # Longer queries can check clean_source or source_raw
                if v.lower() in clean_source.lower():
                    score, match_field, matched_term = 250.0, "Content (विवरण)", v
                    break
                elif v.lower() in source_raw.lower():
                    score, match_field, matched_term = 200.0, "Template / Label", v
                    break

    if score > 0.0:
        return (score, match_field, matched_term, format_record_snippet(rec, matched_term))
    return (0.0, "", "", "")


class Repository:
    """Repository class for CRUD operations on the database."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def _now(self) -> str:
        return datetime.now().isoformat()

    # --- Documents ---

    def add_document(self, name: str, file_path: str, page_count: int, doc_type: PageType, file_size: int) -> Optional[Document]:
        now = self._now()
        sql = """
            INSERT INTO documents (name, file_path, page_count, doc_type, file_size, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        doc_id = self.db.execute(sql, (name, file_path, page_count, doc_type.value, file_size, now, now))
        if doc_id:
            return self.get_document(doc_id)
        return None

    def get_document(self, doc_id: int) -> Optional[Document]:
        sql = "SELECT id, name, file_path, page_count, doc_type, file_size, created_at, updated_at FROM documents WHERE id = ?"
        row = self.db.fetchone(sql, (doc_id,))
        return Document.from_row(row) if row else None

    def get_all_documents(self) -> List[Document]:
        sql = "SELECT id, name, file_path, page_count, doc_type, file_size, created_at, updated_at FROM documents ORDER BY updated_at DESC"
        rows = self.db.fetchall(sql)
        return [Document.from_row(row) for row in rows if row]

    def update_document(self, doc_id: int, **kwargs) -> bool:
        if not kwargs:
            return True
        kwargs['updated_at'] = self._now()
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = tuple(kwargs.values()) + (doc_id,)
        sql = f"UPDATE documents SET {set_clause} WHERE id = ?"
        self.db.execute(sql, values)
        return True

    def delete_document(self, doc_id: int) -> bool:
        sql = "DELETE FROM documents WHERE id = ?"
        self.db.execute(sql, (doc_id,))
        return True

    # --- Pages ---

    def add_page(self, document_id: int, page_number: int, raw_text: str, processed_text: str,
                 page_type: PageType, ocr_confidence: Optional[float], width: float, height: float, has_tables: bool) -> Optional[Page]:
        clean_raw = normalize_devanagari(raw_text or "")
        clean_proc = normalize_devanagari(processed_text or "")
        sql = """
            INSERT INTO pages (document_id, page_number, raw_text, processed_text, page_type, ocr_confidence, width, height, has_tables)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        page_id = self.db.execute(sql, (
            document_id, page_number, clean_raw, clean_proc, page_type.value,
            ocr_confidence, width, height, 1 if has_tables else 0
        ))
        if page_id:
            return self.get_page(page_id)
        return None

    def get_page(self, page_id: int) -> Optional[Page]:
        sql = "SELECT id, document_id, page_number, raw_text, processed_text, page_type, ocr_confidence, width, height, has_tables FROM pages WHERE id = ?"
        row = self.db.fetchone(sql, (page_id,))
        return Page.from_row(row) if row else None

    def get_pages_by_document(self, doc_id: int) -> List[Page]:
        sql = "SELECT id, document_id, page_number, raw_text, processed_text, page_type, ocr_confidence, width, height, has_tables FROM pages WHERE document_id = ? ORDER BY page_number ASC"
        rows = self.db.fetchall(sql, (doc_id,))
        return [Page.from_row(row) for row in rows if row]

    def get_all_pages(self) -> List[Page]:
        sql = "SELECT id, document_id, page_number, raw_text, processed_text, page_type, ocr_confidence, width, height, has_tables FROM pages ORDER BY document_id ASC, page_number ASC"
        rows = self.db.fetchall(sql)
        return [Page.from_row(row) for row in rows if row]

    def get_page_by_number(self, doc_id: int, page_number: int) -> Optional[Page]:
        sql = "SELECT id, document_id, page_number, raw_text, processed_text, page_type, ocr_confidence, width, height, has_tables FROM pages WHERE document_id = ? AND page_number = ?"
        row = self.db.fetchone(sql, (doc_id, page_number))
        return Page.from_row(row) if row else None

    def update_page(self, page_id: int, **kwargs) -> bool:
        if not kwargs:
            return True
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = tuple(kwargs.values()) + (page_id,)
        sql = f"UPDATE pages SET {set_clause} WHERE id = ?"
        self.db.execute(sql, values)
        return True

    # --- Records ---

    def add_record(self, document_id: int, page_number: int, category_id: Optional[int], data: dict,
                   source_text: str, bbox_x: float, bbox_y: float, bbox_w: float, bbox_h: float) -> Optional[Record]:
        now = self._now()
        clean_data = {}
        if data:
            for k, v in data.items():
                if isinstance(v, str):
                    clean_data[k] = normalize_devanagari(v)
                else:
                    clean_data[k] = v
        data_json = json.dumps(clean_data) if clean_data else "{}"
        clean_source = normalize_devanagari(source_text or "")
        sql = """
            INSERT INTO records (document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """
        rec_id = self.db.execute(sql, (
            document_id, page_number, category_id, data_json, clean_source,
            bbox_x, bbox_y, bbox_w, bbox_h, now, now
        ))
        
        if category_id:
            self.update_category_counts(document_id)
            
        if rec_id:
            return self.get_record(rec_id)
        return None

    def get_record(self, record_id: int) -> Optional[Record]:
        sql = "SELECT id, document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited FROM records WHERE id = ?"
        row = self.db.fetchone(sql, (record_id,))
        return Record.from_row(row) if row else None

    def get_records_by_document(self, doc_id: int, category_id: Optional[int] = None, page_number: Optional[int] = None,
                                sort_by: Optional[str] = None, sort_order: str = 'ASC', limit: Optional[int] = None, offset: Optional[int] = None) -> List[Record]:
        query = "SELECT id, document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited FROM records WHERE document_id = ?"
        params = [doc_id]
        
        if category_id is not None:
            query += " AND category_id = ?"
            params.append(category_id)
            
        if page_number is not None:
            query += " AND page_number = ?"
            params.append(page_number)
            
        if sort_by in ['page_number', 'created_at', 'updated_at']:
            direction = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
            query += f" ORDER BY {sort_by} {direction}"
        else:
            query += " ORDER BY page_number ASC"
            
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)
                
        rows = self.db.fetchall(query, tuple(params))
        return [Record.from_row(row) for row in rows if row]

    def get_records_by_category(self, category_id: int) -> List[Record]:
        sql = "SELECT id, document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited FROM records WHERE category_id = ? ORDER BY page_number ASC"
        rows = self.db.fetchall(sql, (category_id,))
        return [Record.from_row(row) for row in rows if row]

    def get_all_records(self, doc_id: Optional[int] = None) -> List[Record]:
        if doc_id is not None:
            return self.get_records_by_document(doc_id)
        sql = "SELECT id, document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited FROM records ORDER BY page_number ASC"
        rows = self.db.fetchall(sql)
        return [Record.from_row(row) for row in rows if row]

    def get_records_by_ids(self, record_ids: List[int]) -> List[Record]:
        if not record_ids:
            return []
        placeholders = ",".join(["?"] * len(record_ids))
        sql = f"SELECT id, document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited FROM records WHERE id IN ({placeholders}) ORDER BY page_number ASC"
        rows = self.db.fetchall(sql, tuple(record_ids))
        return [Record.from_row(row) for row in rows if row]

    def search_records(self, query: str, doc_id: Optional[int] = None) -> List[Record]:
        search_results = self.search(query, doc_id)
        record_ids = [r.record_id for r in search_results if r.record_id is not None]
        if not record_ids:
            pattern = f"%{query}%"
            if doc_id is not None:
                sql = "SELECT id, document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited FROM records WHERE document_id = ? AND (source_text LIKE ? OR data LIKE ?) ORDER BY page_number ASC"
                rows = self.db.fetchall(sql, (doc_id, pattern, pattern))
            else:
                sql = "SELECT id, document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited FROM records WHERE source_text LIKE ? OR data LIKE ? ORDER BY page_number ASC"
                rows = self.db.fetchall(sql, (pattern, pattern))
            return [Record.from_row(row) for row in rows if row]
        return self.get_records_by_ids(record_ids)


    def update_record(self, record_id: int, **kwargs) -> bool:
        if not kwargs:
            return True
        kwargs['updated_at'] = self._now()
        if 'data' in kwargs and isinstance(kwargs['data'], dict):
            kwargs['data'] = json.dumps(kwargs['data'])
            
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = tuple(kwargs.values()) + (record_id,)
        sql = f"UPDATE records SET {set_clause} WHERE id = ?"
        self.db.execute(sql, values)
        return True

    def delete_record(self, record_id: int) -> bool:
        # Get document_id first to update counts later
        record = self.get_record(record_id)
        if not record:
            return False
            
        sql = "DELETE FROM records WHERE id = ?"
        self.db.execute(sql, (record_id,))
        self.update_category_counts(record.document_id)
        return True

    def delete_records(self, record_ids: List[int]) -> bool:
        if not record_ids:
            return True
            
        placeholders = ",".join(["?"] * len(record_ids))
        
        # Get document_ids to update counts
        doc_sql = f"SELECT DISTINCT document_id FROM records WHERE id IN ({placeholders})"
        doc_rows = self.db.fetchall(doc_sql, tuple(record_ids))
        doc_ids = [row[0] for row in doc_rows]
        
        sql = f"DELETE FROM records WHERE id IN ({placeholders})"
        self.db.execute(sql, tuple(record_ids))
        
        for d_id in doc_ids:
            self.update_category_counts(d_id)
            
        return True

    def move_records_to_category(self, record_ids: List[int], category_id: int) -> bool:
        if not record_ids:
            return True
            
        placeholders = ",".join(["?"] * len(record_ids))
        
        # Get document_ids
        doc_sql = f"SELECT DISTINCT document_id FROM records WHERE id IN ({placeholders})"
        doc_rows = self.db.fetchall(doc_sql, tuple(record_ids))
        doc_ids = [row[0] for row in doc_rows]
        
        sql = f"UPDATE records SET category_id = ?, updated_at = ? WHERE id IN ({placeholders})"
        params = (category_id, self._now()) + tuple(record_ids)
        self.db.execute(sql, params)
        
        for d_id in doc_ids:
            self.update_category_counts(d_id)
            
        return True

    def get_record_count(self, doc_id: int, category_id: Optional[int] = None) -> int:
        if category_id is not None:
            sql = "SELECT COUNT(*) FROM records WHERE document_id = ? AND category_id = ?"
            row = self.db.fetchone(sql, (doc_id, category_id))
        else:
            sql = "SELECT COUNT(*) FROM records WHERE document_id = ?"
            row = self.db.fetchone(sql, (doc_id,))
        return row[0] if row else 0

    def get_all_field_names(self, doc_id: int) -> List[str]:
        sql = "SELECT data FROM records WHERE document_id = ?"
        rows = self.db.fetchall(sql, (doc_id,))
        keys = set()
        for row in rows:
            if row and row[0]:
                try:
                    data = json.loads(row[0])
                    if isinstance(data, dict):
                        keys.update(data.keys())
                except json.JSONDecodeError:
                    pass
        return sorted(list(keys))

    # --- Categories ---

    def add_category(self, document_id: int, name: str, parent_id: Optional[int] = None, color: Optional[str] = None) -> Optional[Category]:
        sql = "INSERT INTO categories (document_id, name, parent_id, color, record_count, sort_order) VALUES (?, ?, ?, ?, 0, 0)"
        cat_id = self.db.execute(sql, (document_id, name, parent_id, color))
        if cat_id:
            return self.get_category(cat_id)
        return None

    def get_category(self, cat_id: int) -> Optional[Category]:
        sql = "SELECT id, document_id, name, parent_id, record_count, color, sort_order FROM categories WHERE id = ?"
        row = self.db.fetchone(sql, (cat_id,))
        return Category.from_row(row) if row else None

    def get_categories(self, doc_id: Optional[int] = None) -> List[Category]:
        if doc_id is not None:
            return self.get_categories_by_document(doc_id)
        sql = "SELECT id, document_id, name, parent_id, record_count, color, sort_order FROM categories ORDER BY sort_order ASC, name ASC"
        rows = self.db.fetchall(sql)
        return [Category.from_row(row) for row in rows if row]

    def get_categories_by_document(self, doc_id: int) -> List[Category]:
        sql = "SELECT id, document_id, name, parent_id, record_count, color, sort_order FROM categories WHERE document_id = ? ORDER BY sort_order ASC, name ASC"
        rows = self.db.fetchall(sql, (doc_id,))
        return [Category.from_row(row) for row in rows if row]

    def get_child_categories(self, parent_id: int) -> List[Category]:
        sql = "SELECT id, document_id, name, parent_id, record_count, color, sort_order FROM categories WHERE parent_id = ? ORDER BY sort_order ASC, name ASC"
        rows = self.db.fetchall(sql, (parent_id,))
        return [Category.from_row(row) for row in rows if row]

    def update_category(self, cat_id: int, **kwargs) -> bool:
        if not kwargs:
            return True
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = tuple(kwargs.values()) + (cat_id,)
        sql = f"UPDATE categories SET {set_clause} WHERE id = ?"
        self.db.execute(sql, values)
        return True

    def delete_category(self, cat_id: int) -> bool:
        cat = self.get_category(cat_id)
        if not cat:
            return False
            
        sql = "DELETE FROM categories WHERE id = ?"
        self.db.execute(sql, (cat_id,))
        self.update_category_counts(cat.document_id)
        return True

    def merge_categories(self, source_ids: List[int], target_id: int) -> bool:
        if not source_ids:
            return True
            
        target_cat = self.get_category(target_id)
        if not target_cat:
            return False
            
        placeholders = ",".join(["?"] * len(source_ids))
        
        # Move records
        sql_update = f"UPDATE records SET category_id = ?, updated_at = ? WHERE category_id IN ({placeholders})"
        params = (target_id, self._now()) + tuple(source_ids)
        self.db.execute(sql_update, params)
        
        # Delete old categories
        sql_delete = f"DELETE FROM categories WHERE id IN ({placeholders})"
        self.db.execute(sql_delete, tuple(source_ids))
        
        self.update_category_counts(target_cat.document_id)
        return True

    def update_category_counts(self, doc_id: int) -> bool:
        sql = """
            UPDATE categories 
            SET record_count = (
                SELECT COUNT(*) FROM records WHERE records.category_id = categories.id
            )
            WHERE document_id = ?
        """
        self.db.execute(sql, (doc_id,))
        return True

    # --- Search ---

    def add_to_search_index(self, text: str, page_number: int, document_id: int, record_id: Optional[int] = None, category_name: str = '') -> bool:
        sql = "INSERT INTO search_index (text, page_number, document_id, record_id, category_name) VALUES (?, ?, ?, ?, ?)"
        self.db.execute(sql, (text, page_number, document_id, record_id, category_name))
        return True

    def clear_fts_index(self, doc_id: int):
        self.db.execute("DELETE FROM search_index WHERE document_id = ?", (doc_id,))

    def rebuild_search_index(self, doc_id: int) -> bool:
        # Clear existing
        self.clear_fts_index(doc_id)
        
        # Add pages (only add raw page text for pages that do not have records, to prevent duplicate raw text matches)
        pages = self.get_pages_by_document(doc_id)
        records = self.get_records_by_document(doc_id)
        pages_with_records = set(r.page_number for r in records)

        for page in pages:
            if page.page_number not in pages_with_records:
                if page.processed_text or page.raw_text:
                    self.add_to_search_index(
                        page.processed_text or page.raw_text, 
                        page.page_number, 
                        doc_id
                    )
                
        # Add records
        for rec in records:
            cat_name = ""
            if rec.category_id:
                cat = self.get_category(rec.category_id)
                if cat:
                    cat_name = cat.name
                    
            text_to_index = rec.source_text or ""
            if rec.data:
                # Add clean values from data dict
                text_to_index += " " + " ".join([str(v) for v in rec.data.values() if v])
                
            if text_to_index.strip():
                self.add_to_search_index(
                    text_to_index,
                    rec.page_number,
                    doc_id,
                    rec.id,
                    cat_name
                )
        return True

    def _make_snippet(self, text: str, match_term: str, window: int = 40) -> str:
        return _make_snippet(text, match_term, window)

    def _prepare_fts_query(self, query: str) -> str:
        """Prepare and sanitize a query for SQLite FTS5 prefix search."""
        clean = query.strip()
        if not clean:
            return ""
        tokens = [t.strip('"\'-.,;:!?()[]{}') for t in clean.split()]
        tokens = [t for t in tokens if t]
        if not tokens:
            return f'"{clean}"'
        parts = [f'"{t.replace(chr(34), chr(34)+chr(34))}"*' for t in tokens]
        return " ".join(parts)

    def search(self, query: str, document_id: Optional[int] = None, limit: int = 500, scope: str = 'all') -> List[SearchResult]:
        if not query or not query.strip():
            return []
            
        raw_q = query.strip()
        is_prefix = raw_q.endswith('*')
        clean_q = raw_q.rstrip('*').strip()
        if not clean_q:
            clean_q = raw_q

        scope_norm = scope.lower().strip()
        if 'name' in scope_norm or 'नाम' in scope_norm:
            scope_key = 'name'
        elif 'voter' in scope_norm or 'epic' in scope_norm or 'id' in scope_norm or 'पहचान' in scope_norm:
            scope_key = 'voter_id'
        elif 'exact' in scope_norm or 'सटीक' in scope_norm:
            scope_key = 'exact'
        else:
            scope_key = 'all'

        variants = get_hindi_search_variants(clean_q)
        results: List[SearchResult] = []
        matched_record_pages = set()
        seen_keys = set()

        # 1. Search Records with precision scoring and boilerplate suppression
        records = self.get_records_by_document(document_id) if document_id is not None else self.get_all_records()
        for rec in records:
            score, match_field, matched_term, snippet = score_record_match(rec, clean_q, variants, scope)
            if score > 0.0:
                key = (rec.page_number, rec.id)
                if key not in seen_keys:
                    seen_keys.add(key)
                    cat_name = ""
                    if rec.category_id:
                        cat = self.get_category(rec.category_id)
                        if cat:
                            cat_name = cat.name
                    results.append(SearchResult(
                        text=rec.source_text or "",
                        page_number=rec.page_number,
                        category_name=cat_name,
                        context_snippet=snippet,
                        record_id=rec.id,
                        rank=score,
                        match_field=match_field
                    ))
                    matched_record_pages.add(rec.page_number)

        # 2. Search Pages (for pages that don't have records or non-record documents)
        if scope_key in ('all', 'exact') and len(results) < limit:
            pages = self.get_pages_by_document(document_id) if document_id is not None else self.get_all_pages()
            for page in pages:
                if page.page_number in matched_record_pages:
                    continue
                p_txt = page.processed_text or page.raw_text or ""
                if not p_txt.strip():
                    continue
                clean_p = strip_boilerplate_labels(p_txt)
                matched_v = None
                p_score = 0.0
                m_field = "Page Text"

                for v in variants:
                    if not v:
                        continue
                    if scope_key == 'exact':
                        if re.search(r'(?:\b|^|\s)' + re.escape(v) + r'(?:\b|$|\s)', clean_p, re.IGNORECASE):
                            matched_v = v
                            p_score = 150.0
                            m_field = "Exact Word"
                            break
                    else:
                        # For short queries (<= 3 chars, like 'म'), search clean text to avoid boilerplate
                        target = clean_p if len(clean_q) <= 3 else p_txt
                        if v.lower() in target.lower():
                            matched_v = v
                            p_score = 100.0
                            break
                        elif len(clean_q) > 3 and v.lower() in p_txt.lower():
                            matched_v = v
                            p_score = 80.0
                            break

                if p_score > 0.0 and matched_v:
                    key = (page.page_number, None)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        snippet = self._make_snippet(clean_p or p_txt, matched_v)
                        results.append(SearchResult(
                            text=p_txt[:200],
                            page_number=page.page_number,
                            category_name="",
                            context_snippet=snippet,
                            record_id=None,
                            rank=p_score,
                            match_field=m_field
                        ))

        # 3. Fallback to FTS5 if no results found and query has >= 2 characters (only for 'all' scope)
        if not results and len(clean_q) >= 2 and scope_key == 'all':
            fts_query = self._prepare_fts_query(clean_q)
            sql = """
                SELECT 
                    text, 
                    page_number, 
                    category_name, 
                    snippet(search_index, 0, '<b>', '</b>', '...', 64) as context_snippet, 
                    record_id,
                    rank
                FROM search_index 
                WHERE search_index MATCH ? 
            """
            params: List[Any] = [fts_query]
            if document_id is not None:
                sql += " AND document_id = ?"
                params.append(document_id)
            sql += " ORDER BY page_number ASC, rank ASC LIMIT ?"
            params.append(limit)
            try:
                rows = self.db.fetchall(sql, tuple(params))
                for row in rows:
                    if row:
                        key = (row[1], row[4])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            results.append(SearchResult(
                                text=row[0],
                                page_number=row[1],
                                category_name=row[2] if row[2] else "",
                                context_snippet=row[3],
                                record_id=row[4],
                                rank=50.0,
                                match_field="FTS"
                            ))
            except Exception:
                pass

        # Sort results: sequential page order first, then highest relevance rank on that page, then record_id
        results.sort(key=lambda r: (r.page_number, -r.rank, r.record_id or 0))
        return results[:limit]

    def search_in_category(self, query: str, category_id: int, limit: int = 500, scope: str = 'all') -> List[SearchResult]:
        cat = self.get_category(category_id)
        if not cat:
            return []
            
        clean_q = query.rstrip('*').strip()
        if not clean_q:
            clean_q = query.strip()
        variants = get_hindi_search_variants(clean_q)
        results: List[SearchResult] = []
        seen_keys = set()

        records = self.get_records_by_category(category_id)
        for rec in records:
            score, match_field, matched_term, snippet = score_record_match(rec, clean_q, variants, scope)
            if score > 0.0:
                key = (rec.page_number, rec.id)
                if key not in seen_keys:
                    seen_keys.add(key)
                    results.append(SearchResult(
                        text=rec.source_text or "",
                        page_number=rec.page_number,
                        category_name=cat.name,
                        context_snippet=snippet,
                        record_id=rec.id,
                        rank=score,
                        match_field=match_field
                    ))

        # Fallback to FTS index filtered by category_name if no records found
        if not results and len(clean_q) >= 2:
            fts_query = self._prepare_fts_query(clean_q)
            sql = """
                SELECT 
                    text, 
                    page_number, 
                    category_name, 
                    snippet(search_index, 0, '<b>', '</b>', '...', 64) as context_snippet, 
                    record_id,
                    rank
                FROM search_index 
                WHERE search_index MATCH ? AND category_name = ?
                ORDER BY page_number ASC, rank ASC LIMIT ?
            """
            try:
                rows = self.db.fetchall(sql, (fts_query, cat.name, limit))
                for row in rows:
                    if row:
                        key = (row[1], row[4])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            results.append(SearchResult(
                                text=row[0],
                                page_number=row[1],
                                category_name=row[2] if row[2] else "",
                                context_snippet=row[3],
                                record_id=row[4],
                                rank=50.0,
                                match_field="Category FTS"
                            ))
            except Exception:
                pass

        results.sort(key=lambda r: (r.page_number, -r.rank, r.record_id or 0))
        return results[:limit]

    def find_bounding_boxes_for_text(self, document_id: int, page_number: int, query: str) -> List[Tuple[float, float, float, float]]:
        """Find bounding boxes for words or phrases matching query on a page.
        Prioritizes word-level bounding boxes, then block-level, then record coordinates."""
        page = self.get_page_by_number(document_id, page_number)
        if not page:
            return []

        clean_q = normalize_devanagari(query.strip())
        variants = get_hindi_search_variants(clean_q)
        boxes = []

        # 1. First priority: Exact word-level bounding boxes (block_type = 'word')
        sql_word = """
            SELECT x0, y0, x1, y1, text FROM bounding_boxes 
            WHERE page_id = ? AND block_type = 'word'
        """
        word_rows = self.db.fetchall(sql_word, (page.id,))
        for r in word_rows:
            if r and r[4]:
                w_norm = normalize_devanagari(r[4])
                for v in variants:
                    if v and (w_norm.lower() == v.lower() or v.lower() in w_norm.lower()):
                        box = (float(r[0]), float(r[1]), float(r[2]), float(r[3]))
                        if box not in boxes:
                            boxes.append(box)
                        break

        if boxes:
            return boxes

        # 2. Second priority: Line or block-level bounding boxes
        sql_block = """
            SELECT x0, y0, x1, y1, text FROM bounding_boxes 
            WHERE page_id = ?
        """
        block_rows = self.db.fetchall(sql_block, (page.id,))
        for r in block_rows:
            if r and r[4]:
                b_norm = normalize_devanagari(r[4])
                for v in variants:
                    if v and v.lower() in b_norm.lower():
                        box = (float(r[0]), float(r[1]), float(r[2]), float(r[3]))
                        if box not in boxes:
                            boxes.append(box)
                        break

        # Try individual words if query is multi-word
        words = clean_q.split()
        if len(words) > 1 and not boxes:
            for w in words:
                if len(w) >= 2:
                    w_variants = get_hindi_search_variants(w)
                    for r in block_rows:
                        if r and r[4]:
                            b_norm = normalize_devanagari(r[4])
                            for wv in w_variants:
                                if wv and wv.lower() in b_norm.lower():
                                    box = (float(r[0]), float(r[1]), float(r[2]), float(r[3]))
                                    if box not in boxes:
                                        boxes.append(box)
                                    break

        if boxes:
            return boxes

        # 3. Third priority: Check records table on this page (essential for card grids / voter lists)
        try:
            rec_sql = """
                SELECT bbox_x, bbox_y, bbox_w, bbox_h, source_text, data FROM records
                WHERE document_id = ? AND page_number = ?
            """
            rec_rows = self.db.fetchall(rec_sql, (document_id, page_number))
            for rr in rec_rows:
                if rr and (rr[0] or rr[1] or rr[2] or rr[3]):
                    s_txt = normalize_devanagari(rr[4] or "")
                    d_txt = normalize_devanagari(rr[5] or "")
                    if any(v.lower() in s_txt.lower() or v.lower() in d_txt.lower() for v in variants if v):
                        x0 = float(rr[0])
                        y0 = float(rr[1])
                        x1 = x0 + float(rr[2])
                        y1 = y0 + float(rr[3])
                        box = (x0, y0, x1, y1)
                        if box not in boxes:
                            boxes.append(box)
        except Exception:
            pass

        return boxes

    # --- Bounding Boxes ---

    def add_bounding_box(self, page_id: int, text: str, x0: float, y0: float, x1: float, y1: float, block_type: str) -> Optional[BoundingBox]:
        clean_text = normalize_devanagari(text or "")
        sql = "INSERT INTO bounding_boxes (page_id, text, x0, y0, x1, y1, block_type) VALUES (?, ?, ?, ?, ?, ?, ?)"
        bb_id = self.db.execute(sql, (page_id, clean_text, x0, y0, x1, y1, block_type))
        if bb_id:
            return self.find_bounding_box_by_id(bb_id)
        return None
        
    def find_bounding_box_by_id(self, bb_id: int) -> Optional[BoundingBox]:
        sql = "SELECT id, page_id, text, x0, y0, x1, y1, block_type FROM bounding_boxes WHERE id = ?"
        row = self.db.fetchone(sql, (bb_id,))
        return BoundingBox.from_row(row) if row else None

    def get_bounding_boxes_by_page(self, page_id: int) -> List[BoundingBox]:
        sql = "SELECT id, page_id, text, x0, y0, x1, y1, block_type FROM bounding_boxes WHERE page_id = ?"
        rows = self.db.fetchall(sql, (page_id,))
        return [BoundingBox.from_row(row) for row in rows if row]

    def find_bounding_box_for_text(self, page_id: int, search_text: str) -> Optional[BoundingBox]:
        sql = "SELECT id, page_id, text, x0, y0, x1, y1, block_type FROM bounding_boxes WHERE page_id = ? AND text LIKE ? LIMIT 1"
        row = self.db.fetchone(sql, (page_id, f"%{search_text}%"))
        return BoundingBox.from_row(row) if row else None

    # --- User Corrections ---

    def add_correction(self, record_id: int, field_name: str, original_value: str, corrected_value: str) -> Optional[UserCorrection]:
        now = self._now()
        sql = "INSERT INTO user_corrections (record_id, field_name, original_value, corrected_value, created_at) VALUES (?, ?, ?, ?, ?)"
        uc_id = self.db.execute(sql, (record_id, field_name, original_value, corrected_value, now))
        if uc_id:
            row = self.db.fetchone("SELECT id, record_id, field_name, original_value, corrected_value, created_at FROM user_corrections WHERE id = ?", (uc_id,))
            return UserCorrection.from_row(row) if row else None
        return None

    def get_corrections_by_record(self, record_id: int) -> List[UserCorrection]:
        sql = "SELECT id, record_id, field_name, original_value, corrected_value, created_at FROM user_corrections WHERE record_id = ? ORDER BY created_at DESC"
        rows = self.db.fetchall(sql, (record_id,))
        return [UserCorrection.from_row(row) for row in rows if row]

    # --- Table Data ---

    def add_table_data(self, page_id: int, document_id: int, page_number: int, headers: List[str], rows: List[List[str]], bbox: Tuple[float, float, float, float]) -> Optional[TableData]:
        headers_json = json.dumps(headers)
        rows_json = json.dumps(rows)
        bbox_x, bbox_y, bbox_w, bbox_h = bbox
        
        sql = """
            INSERT INTO table_data (page_id, document_id, page_number, headers, rows, bbox_x, bbox_y, bbox_w, bbox_h)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        td_id = self.db.execute(sql, (page_id, document_id, page_number, headers_json, rows_json, bbox_x, bbox_y, bbox_w, bbox_h))
        if td_id:
            row = self.db.fetchone("SELECT id, page_id, document_id, page_number, headers, rows, bbox_x, bbox_y, bbox_w, bbox_h FROM table_data WHERE id = ?", (td_id,))
            return TableData.from_row(row) if row else None
        return None

    def get_tables_by_document(self, doc_id: int) -> List[TableData]:
        sql = "SELECT id, page_id, document_id, page_number, headers, rows, bbox_x, bbox_y, bbox_w, bbox_h FROM table_data WHERE document_id = ? ORDER BY page_number ASC"
        rows = self.db.fetchall(sql, (doc_id,))
        return [TableData.from_row(row) for row in rows if row]

    def get_tables_by_page(self, doc_id: int, page_number: int) -> List[TableData]:
        sql = "SELECT id, page_id, document_id, page_number, headers, rows, bbox_x, bbox_y, bbox_w, bbox_h FROM table_data WHERE document_id = ? AND page_number = ?"
        rows = self.db.fetchall(sql, (doc_id, page_number))
        return [TableData.from_row(row) for row in rows if row]

    # --- Project Meta ---

    def set_meta(self, key: str, value: str) -> bool:
        sql = "INSERT INTO project_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?"
        self.db.execute(sql, (key, value, value))
        return True

    def get_meta(self, key: str) -> Optional[str]:
        sql = "SELECT value FROM project_meta WHERE key = ?"
        row = self.db.fetchone(sql, (key,))
        return row[0] if row else None

    def get_all_meta(self) -> dict:
        sql = "SELECT key, value FROM project_meta"
        rows = self.db.fetchall(sql)
        return {row[0]: row[1] for row in rows if row}

    # --- Filtering ---

    def get_filtered_records(self, doc_id: int, filters: dict) -> List[Record]:
        query = "SELECT id, document_id, page_number, category_id, data, source_text, bbox_x, bbox_y, bbox_w, bbox_h, created_at, updated_at, is_edited FROM records WHERE document_id = ?"
        params: List[Any] = [doc_id]
        
        if 'category_id' in filters:
            query += " AND category_id = ?"
            params.append(filters['category_id'])
            
        if 'page_number' in filters:
            query += " AND page_number = ?"
            params.append(filters['page_number'])
            
        if 'page_range' in filters and isinstance(filters['page_range'], tuple) and len(filters['page_range']) == 2:
            query += " AND page_number BETWEEN ? AND ?"
            params.append(filters['page_range'][0])
            params.append(filters['page_range'][1])
            
        if 'has_corrections' in filters and filters['has_corrections']:
            query += " AND id IN (SELECT record_id FROM user_corrections)"
            
        query += " ORDER BY page_number ASC"
        
        rows = self.db.fetchall(query, tuple(params))
        records = [Record.from_row(row) for row in rows if row]
        
        # Apply precision search_query filtering using score_record_match
        if 'search_query' in filters and filters['search_query']:
            sq = filters['search_query'].strip()
            sq_variants = get_hindi_search_variants(sq)
            scope = filters.get('scope', 'all')
            filtered = []
            for r in records:
                score, _, _, _ = score_record_match(r, sq, sq_variants, scope)
                if score > 0.0:
                    filtered.append(r)
            records = filtered
            
        if 'field_filters' in filters and isinstance(filters['field_filters'], dict):
            for k, v in filters['field_filters'].items():
                v_str = str(v).lower()
                records = [r for r in records if r.data and k in r.data and str(r.data[k]).lower() == v_str]
                
        return records

