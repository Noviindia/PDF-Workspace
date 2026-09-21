"""
PDF Workspace - Record Extractor
Extracts structured records from tables, key-value pairs, and multi-card layouts
such as Indian Electoral Rolls, PACS Member Registers, and Form Grids (Hindi + English).
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from app.database.repository import normalize_devanagari


@dataclass
class ExtractedRecord:
    data: Dict[str, Any]
    page_number: int
    source_text: str
    bbox: Tuple[float, float, float, float]
    category_hint: Optional[str] = None


class RecordExtractor:
    """Extracts structured records from tables, multi-column card grids, and text."""

    def __init__(self):
        self._voter_keywords = [
            'निर्वाचक', 'मतदाता', 'अनुभाग संख्या', 'विधान सभा', 'विधानसभा',
            'वोटर', 'elector', 'voter list', 'electoral roll', 'pacs',
            'प्राथमिक कृषि साख', 'पैक्स', 'सदस्यता सूची', 'मतदाता सूची',
            'electoral roll'
        ]

    def is_voter_list_content(self, text: str) -> bool:
        """Detect whether text belongs to an Electoral Roll, Voter List, or Member Register."""
        if not text:
            return False
        text_lower = text.lower()
        for kw in self._voter_keywords:
            if kw in text_lower:
                return True
        # Check for multiple occurrences of voter card field markers
        matches = len(re.findall(r'(?:निर्वाचक|मतदाता|सदस्य)?\s*का?\s*नाम\s*[:\-\=]', text))
        if matches >= 2:
            return True
        # Check for EPIC ID pattern matches
        epic_matches = len(re.findall(r'\b[A-Z]{3}[0-9]{7}\b', text))
        return epic_matches >= 2

    def extract_from_tables(self, tables: List, page_number: int) -> List[ExtractedRecord]:
        """Extract records from tables."""
        records = []
        for table in tables:
            raw_headers = [h.strip() for h in table.headers if str(h).strip()]
            if not raw_headers:
                continue

            headers = [self._normalize_field_name(h) for h in table.headers]
            for row in table.rows:
                data = {}
                for idx, cell in enumerate(row):
                    if idx < len(headers) and headers[idx]:
                        cell_val = normalize_devanagari(str(cell).strip())
                        if cell_val:
                            data[headers[idx]] = cell_val
                if data:
                    records.append(ExtractedRecord(
                        data=data,
                        page_number=page_number,
                        source_text=normalize_devanagari(" | ".join(str(c) for c in row if str(c).strip())),
                        bbox=table.bbox if hasattr(table, 'bbox') else (0.0, 0.0, 0.0, 0.0),
                        category_hint=None
                    ))
        return records

    def extract_voter_cards(self, text: str, page_number: int, blocks: Optional[List] = None) -> List[ExtractedRecord]:
        """Extract individual voter cards from a page of an Electoral Roll / Register.
        
        Supports:
        1. Spatial block clustering (when bounding-box blocks from OCR are available)
        2. Horizontal cross-column line decomposition
        3. Sequential text card-boundary splitting
        """
        records: List[ExtractedRecord] = []

        # Strategy 1: Spatial block clustering if blocks with coordinates are available
        if blocks and len(blocks) >= 2:
            spatial_records = self._extract_voter_cards_from_blocks(blocks, page_number)
            if spatial_records:
                return spatial_records

        # Strategy 2: Horizontal multi-column line decomposition
        horizontal_records = self._extract_from_horizontal_matrix(text, page_number)
        if horizontal_records:
            return horizontal_records

        # Strategy 3: Sequential text card boundary splitting
        sequential_records = self._extract_from_card_boundaries(text, page_number)
        if sequential_records:
            return sequential_records

        return records

    def _extract_voter_cards_from_blocks(self, blocks: List, page_number: int) -> List[ExtractedRecord]:
        """Group spatial blocks into columns and sequential voter cards."""
        valid_blocks = [b for b in blocks if hasattr(b, 'text') and b.text.strip()]
        if not valid_blocks:
            return []

        # Find min and max x across all blocks
        min_x = min(b.x0 for b in valid_blocks)
        max_x = max(b.x1 for b in valid_blocks)
        page_w = max_x - min_x
        if page_w <= 0:
            return []

        # Standard Indian voter lists typically have 3 columns (or 2 columns)
        col1_blocks = []
        col2_blocks = []
        col3_blocks = []

        c1_thresh = min_x + page_w * 0.35
        c2_thresh = min_x + page_w * 0.68

        for b in valid_blocks:
            mid_x = (b.x0 + b.x1) / 2.0
            if mid_x < c1_thresh:
                col1_blocks.append(b)
            elif mid_x < c2_thresh:
                col2_blocks.append(b)
            else:
                col3_blocks.append(b)

        # Sort each column top-to-bottom by y0
        col1_blocks.sort(key=lambda b: b.y0)
        col2_blocks.sort(key=lambda b: b.y0)
        col3_blocks.sort(key=lambda b: b.y0)

        all_col_blocks = [col1_blocks, col2_blocks, col3_blocks]
        records: List[ExtractedRecord] = []

        for col_blks in all_col_blocks:
            if not col_blks:
                continue
            col_text = "\n".join([b.text.strip() for b in col_blks])
            col_recs = self._extract_from_card_boundaries(col_text, page_number)
            
            # Map bboxes if possible
            for rec in col_recs:
                matching_b = [b for b in col_blks if rec.data.get('voter_id') and rec.data.get('voter_id') in b.text
                              or rec.data.get('name') and rec.data.get('name') in b.text]
                if matching_b:
                    bx0 = min(b.x0 for b in matching_b)
                    by0 = min(b.y0 for b in matching_b)
                    bx1 = max(b.x1 for b in matching_b)
                    by1 = max(b.y1 for b in matching_b)
                    rec.bbox = (bx0, by0, bx1 - bx0, by1 - by0)
                else:
                    bx0 = min(b.x0 for b in col_blks)
                    bx1 = max(b.x1 for b in col_blks)
                    rec.bbox = (bx0, 0.0, bx1 - bx0, 0.0)
                records.append(rec)

        return records

    def _extract_from_horizontal_matrix(self, text: str, page_number: int) -> List[ExtractedRecord]:
        """Detect and parse lines where multiple card boxes are read horizontally across columns."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return []

        multi_col_lines = 0
        for l in lines:
            if len(re.findall(r'(?:निर्वाचक|मतदाता|सदस्य)?\s*का?\s*नाम\s*[:\-\=]', l)) >= 2:
                multi_col_lines += 1
            elif len(re.findall(r'(?:पिता|पति|माता)\s*का\s*नाम\s*[:\-\=]', l)) >= 2:
                multi_col_lines += 1

        if multi_col_lines < 2:
            return []

        matrix = []
        for l in lines:
            cols = [c.strip() for c in re.split(r'\s{3,}', l) if c.strip()]
            if cols:
                matrix.append(cols)

        if not matrix:
            return []

        max_cols = max(len(row) for row in matrix)
        if max_cols < 2:
            return []

        records = []
        for c_idx in range(max_cols):
            col_lines = [row[c_idx] for row in matrix if c_idx < len(row)]
            col_text = "\n".join(col_lines)
            col_records = self._extract_from_card_boundaries(col_text, page_number)
            records.extend(col_records)

        return records

    def _extract_from_card_boundaries(self, text: str, page_number: int) -> List[ExtractedRecord]:
        """Segment sequential text into individual voter card records."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return []

        card_starts = []
        for idx, line in enumerate(lines):
            if re.match(r'^\d{1,4}\s+[A-Z0-9/]{5,18}\b', line):
                card_starts.append(idx)
            elif re.match(r'^(?:निर्वाचक|मतदाता|सदस्य)?\s*का?\s*नाम\s*[:\-\=]', line, re.IGNORECASE):
                if not (idx > 0 and re.match(r'^\d{1,4}\s+[A-Z0-9/]{5,18}\b', lines[idx - 1])):
                    card_starts.append(idx)
            elif re.match(r'^(?:क्र[०.]?\s*सं[०.]?|क[०.]?\s*सं[०.]?|sl\.?\s*no|serial)\s*[:\-\s]*\d+', line, re.IGNORECASE):
                card_starts.append(idx)

        if not card_starts:
            single_card = self._parse_single_voter_card(text)
            if single_card and (single_card.get('name') or single_card.get('voter_id')):
                return [ExtractedRecord(
                    data=single_card,
                    page_number=page_number,
                    source_text=text[:200],
                    bbox=(0.0, 0.0, 0.0, 0.0)
                )]
            return []

        records = []
        for i, s_idx in enumerate(card_starts):
            e_idx = card_starts[i + 1] if i + 1 < len(card_starts) else len(lines)
            chunk = "\n".join(lines[s_idx:e_idx])
            card_data = self._parse_single_voter_card(chunk)
            if card_data and (card_data.get('name') or card_data.get('voter_id') or card_data.get('serial_no')):
                records.append(ExtractedRecord(
                    data=card_data,
                    page_number=page_number,
                    source_text=chunk[:200],
                    bbox=(0.0, 0.0, 0.0, 0.0)
                ))

        return records

    def _parse_single_voter_card(self, chunk: str) -> Optional[Dict[str, str]]:
        """Parse individual card fields from text block."""
        data = {}

        # 1. Serial No & Voter ID from Header Line (e.g. "1  ABC1234567")
        m_head = re.search(r'^\s*(\d{1,4})\s+([A-Z0-9/]{5,18})\b', chunk, re.MULTILINE)
        if m_head:
            data['serial_no'] = m_head.group(1).strip()
            data['voter_id'] = m_head.group(2).strip()
        else:
            # Separate EPIC / Voter ID pattern
            m_epic = re.search(r'\b([A-Z]{3}[0-9]{7}|[A-Z]{2}/[0-9/]{6,16})\b', chunk)
            if m_epic:
                data['voter_id'] = m_epic.group(1).strip()
            else:
                m_epic_lbl = re.search(r'(?:पहचान\s*पत्र|मतदाता\s*संख्या|epic|id|सदस्यता\s*संख्या|खाता\s*संख्या)\s*[:\-\=\s]*([A-Z0-9/]+)', chunk, re.IGNORECASE)
                if m_epic_lbl:
                    data['voter_id'] = m_epic_lbl.group(1).strip()

            # Separate Serial No pattern
            m_sl = re.search(r'(?:क्र[०.]?\s*सं[०.]?|क[०.]?\s*सं[०.]?|sl\.?\s*no|serial)\s*[:\-\s]*(\d+)', chunk, re.IGNORECASE)
            if m_sl:
                data['serial_no'] = m_sl.group(1).strip()

        # 2. Voter Name
        m_name = re.search(
            r'(?:निर्वाचक\s*का\s*नाम|मतदाता\s*का\s*नाम|सदस्य\s*का\s*नाम|elector\'?s?\s*name|voter\s*name|नाम)\s*[:\-\=\s]\s*([^\n\r\|;]+)',
            chunk, re.IGNORECASE
        )
        if m_name:
            val = m_name.group(1).strip()
            val = re.sub(r'(?:फोटो\s*उपलब्ध\s*है|फोटो\s*उपलब्ध|photo\s*available).*', '', val, flags=re.IGNORECASE).strip()
            val = normalize_devanagari(val)
            if val:
                data['name'] = val

        # 3. Relative / Father's Name
        m_rel = re.search(
            r'(?:(पिता|पति|माता|अभिभावक|संरक्षक)\s*का\s*नाम|father\'?s?\s*name|husband\'?s?\s*name|mother\'?s?\s*name|guardian\'?s?\s*name|सम्बन्धी\s*का\s*नाम)\s*[:\-\=\s]\s*([^\n\r\|;]+)',
            chunk, re.IGNORECASE
        )
        if m_rel:
            rel_type = normalize_devanagari(m_rel.group(1) if m_rel.group(1) else 'पिता')
            data['relation_name'] = normalize_devanagari(m_rel.group(2).strip())
            data['relation_type'] = rel_type

        # 4. House No / Village / Address
        m_house = re.search(
            r'(?:मकान\s*संख्या|गृह\s*संख्या|म[०.]?\s*सं[०.]?|गृह\s*सं[०.]?|ग्राम|पता|वार्ड\s*(?:सं[०.]?|नं[०.]?)?|house\s*(?:no\.?|number)?|address)\s*[:\-\=\s]\s*([^\n\r\|;]+)',
            chunk, re.IGNORECASE
        )
        if m_house:
            data['house_no'] = normalize_devanagari(m_house.group(1).strip())

        # 5. Age
        m_age = re.search(r'(?:उम्र|आयु|age)\s*[:\-\=\s]*([0-9\u0966-\u096f]{1,3})', chunk, re.IGNORECASE)
        if m_age:
            data['age'] = normalize_devanagari(m_age.group(1).strip())

        # 6. Gender
        m_gen = re.search(
            r'(?:लिंग|gender|sex)\s*[:\-\=\s]*(पुरुष|पुरूष|पु[०.]?|महिला|स्त्री|म[०.]?|male|female|m\b|f\b|अन्य|transgender)',
            chunk, re.IGNORECASE
        )
        if m_gen:
            g = m_gen.group(1).strip().lower()
            if re.match(r'^(?:पुरुष|पुरूष|पु[०.]?|male|m)$', g, re.IGNORECASE):
                data['gender'] = 'पुरुष'
            elif re.match(r'^(?:महिला|स्त्री|म[०.]?|female|f)$', g, re.IGNORECASE):
                data['gender'] = 'महिला'
            else:
                data['gender'] = normalize_devanagari(m_gen.group(1).strip())

        return data if data else None

    def extract_from_text(self, text: str, page_number: int) -> List[ExtractedRecord]:
        """Extract records from key-value pairs or voter cards in text."""
        if self.is_voter_list_content(text):
            return self.extract_voter_cards(text, page_number)

        kvps = self._extract_key_value_pairs(text)
        if not kvps:
            return []

        return self._group_kvp_into_records([kvps], text, page_number)

    def _extract_key_value_pairs(self, text: str) -> Dict[str, str]:
        """Extract 'Key: Value' patterns supporting English and Unicode/Devanagari."""
        kvps = {}
        pattern = r'([A-Za-z\u0900-\u097F0-9\s\._\-\/]+)[:\-\=]\s*([^:\n]+)(?=\n|$)'
        for match in re.finditer(pattern, text):
            key = match.group(1).strip()
            value = normalize_devanagari(match.group(2).strip())
            if key and len(key) < 40 and value:
                norm_key = self._normalize_field_name(key)
                if norm_key:
                    kvps[norm_key] = value
        return kvps

    def _normalize_field_name(self, name: str) -> str:
        """Normalize field names while preserving alphanumeric and Devanagari characters."""
        name = name.lower().strip()
        name = re.sub(r'[^\w\u0900-\u097F\s]', '', name)
        name = re.sub(r'\s+', '_', name)
        return name

    def _detect_field_type(self, value: str) -> str:
        """Detect if value is 'number', 'date', 'phone', 'email', 'text'."""
        if re.match(r'^\d+$', value):
            return 'number'
        if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', value):
            return 'email'
        if re.match(r'^\+?\d{10,15}$', re.sub(r'[\s-]', '', value)):
            return 'phone'
        return 'text'

    def _group_kvp_into_records(self, kvps_list: List[Dict], text: str, page_number: int = 1) -> List[ExtractedRecord]:
        """Group key-value pairs into logical records."""
        records = []
        for kvp in kvps_list:
            if kvp:
                records.append(ExtractedRecord(
                    data=kvp,
                    page_number=page_number,
                    source_text=text[:150],
                    bbox=(0.0, 0.0, 0.0, 0.0)
                ))
        return records
