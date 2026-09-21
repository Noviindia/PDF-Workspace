"""
PDF Workspace - Table Detector
Detects and extracts tables from PDF text content.
Works with pure text (no fitz dependency for Android compatibility).
Uses pdfplumber for enhanced table detection when available.
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class DetectedTable:
    """Represents a detected table in a PDF page."""
    headers: List[str]
    rows: List[List[str]]
    page_number: int
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    confidence: float = 0.5

    @property
    def columns(self) -> List[str]:
        return self.headers



class TableDetector:
    """Detect and extract tables from PDF pages.
    
    Uses multiple strategies:
    1. pdfplumber table detection (if available)
    2. Text-based heuristic detection (works everywhere)
    """

    def __init__(self):
        """Initialize table detector."""
        try:
            import pdfplumber
            self._has_pdfplumber = True
        except ImportError:
            self._has_pdfplumber = False

    def detect_tables_from_file(self, file_path: str, page_number: int) -> List[DetectedTable]:
        """Detect tables in a specific page of a PDF file.
        
        Args:
            file_path: Path to PDF file.
            page_number: 1-based page number.
            
        Returns:
            List of detected tables.
        """
        tables = []
        
        # Try PyMuPDF find_tables first (high accuracy)
        try:
            import fitz
            doc = fitz.open(file_path)
            if page_number - 1 < len(doc):
                page = doc[page_number - 1]
                t_tabs = page.find_tables()
                if t_tabs and t_tabs.tables:
                    for tab in t_tabs.tables:
                        raw = tab.extract()
                        if raw and len(raw) > 1:
                            processed = self._process_raw_table(raw, page_number)
                            if processed:
                                bbox = (float(tab.bbox[0]), float(tab.bbox[1]), float(tab.bbox[2]), float(tab.bbox[3])) if hasattr(tab, 'bbox') else (0.0, 0.0, 0.0, 0.0)
                                processed.bbox = bbox
                                processed.confidence = 0.95
                                tables.append(processed)
            doc.close()
            if tables:
                return tables
        except Exception:
            pass

        # Try pdfplumber next (better table detection)
        if self._has_pdfplumber:
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    if page_number - 1 < len(pdf.pages):
                        page = pdf.pages[page_number - 1]
                        extracted = page.extract_tables()
                        if extracted:
                            for table_data in extracted:
                                if table_data and len(table_data) > 1:
                                    table = self._process_raw_table(table_data, page_number)
                                    if table:
                                        tables.append(table)
                        if tables:
                            return tables
            except Exception as e:
                print(f"pdfplumber table detection failed: {e}")

        # Fallback: extract text and detect tables heuristically
        try:
            # Use text extractor to get page text
            from app.core.text_extractor import TextExtractor
            extractor = TextExtractor()
            text = extractor.extract_text_from_file(file_path, page_number - 1)
            if text:
                return self.detect_tables_from_text(text, page_number)
        except Exception as e:
            print(f"Text-based table detection failed: {e}")

        return []

    def detect_tables(self, text: str, page_number: int = 1) -> List[DetectedTable]:
        """Convenience alias for detect_tables_from_text."""
        return self.detect_tables_from_text(text, page_number)

    def detect_tables_from_text(self, text: str, page_number: int) -> List[DetectedTable]:
        """Detect tables from extracted text using heuristics.
        
        Args:
            text: Extracted text from a page.
            page_number: 1-based page number.
            
        Returns:
            List of detected tables.
        """
        if not text or not text.strip():
            return []

        # If this page has Electoral Roll / Voter List card layout, skip heuristic text table detection
        # (Cards will be extracted cleanly by RecordExtractor without generating fragmented tables)
        try:
            from app.core.record_extractor import RecordExtractor
            if RecordExtractor().is_voter_list_content(text):
                return []
        except Exception:
            pass

        tables = []
        lines = text.split('\n')
        
        # Strategy 1: Detect tab-separated or multi-space-separated tables
        tab_table = self._detect_delimited_table(lines, page_number)
        if tab_table:
            tables.append(tab_table)

        # Strategy 2: Detect pipe-separated tables
        pipe_table = self._detect_pipe_table(lines, page_number)
        if pipe_table:
            tables.append(pipe_table)

        # Strategy 3: Detect aligned column tables (most common in PDFs)
        if not tables:
            aligned_tables = self._detect_aligned_table(lines, page_number)
            tables.extend(aligned_tables)

        return tables

    def _detect_delimited_table(self, lines: List[str], page_number: int) -> Optional[DetectedTable]:
        """Detect tables with tab or multi-space delimiters."""
        table_lines = []
        min_columns = 3
        
        for line in lines:
            line = line.strip()
            if not line:
                if len(table_lines) >= 3:
                    break
                table_lines = []
                continue
            
            # Check for tab-separated
            if '\t' in line:
                cells = [c.strip() for c in line.split('\t') if c.strip()]
                if len(cells) >= min_columns:
                    table_lines.append(cells)
                    continue
            
            # Check for multiple-space-separated (3+ spaces)
            cells = [c.strip() for c in re.split(r'\s{3,}', line) if c.strip()]
            if len(cells) >= min_columns:
                table_lines.append(cells)

        if len(table_lines) < 2:
            return None

        # Normalize column count
        max_cols = max(len(row) for row in table_lines)
        normalized = []
        for row in table_lines:
            while len(row) < max_cols:
                row.append('')
            normalized.append(row[:max_cols])

        # First row is likely header if it contains non-numeric values
        headers = normalized[0]
        rows = normalized[1:]

        if self._is_likely_header(headers):
            return DetectedTable(
                headers=headers,
                rows=rows,
                page_number=page_number,
                confidence=0.7
            )
        elif len(table_lines) >= 3:
            auto_headers = [f"Column_{i+1}" for i in range(max_cols)]
            return DetectedTable(
                headers=auto_headers,
                rows=normalized,
                page_number=page_number,
                confidence=0.5
            )
        return None

    def _detect_pipe_table(self, lines: List[str], page_number: int) -> Optional[DetectedTable]:
        """Detect pipe-delimited tables (| col1 | col2 |)."""
        pipe_lines = []
        
        for line in lines:
            line = line.strip()
            if '|' in line:
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if len(cells) >= 2:
                    # Skip separator lines (--- | ---)
                    if all(re.match(r'^[-:]+$', c) for c in cells):
                        continue
                    pipe_lines.append(cells)

        if len(pipe_lines) < 2:
            return None

        max_cols = max(len(row) for row in pipe_lines)
        normalized = []
        for row in pipe_lines:
            while len(row) < max_cols:
                row.append('')
            normalized.append(row[:max_cols])

        return DetectedTable(
            headers=normalized[0],
            rows=normalized[1:],
            page_number=page_number,
            confidence=0.8
        )

    def _detect_aligned_table(self, lines: List[str], page_number: int) -> List[DetectedTable]:
        """Detect tables with aligned columns using position-based heuristics.
        
        This is the most common format in PDF-extracted text where columns
        are aligned by spaces but without consistent delimiters.
        """
        tables = []
        
        # Find groups of lines that look tabular
        current_group = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if len(current_group) >= 3:
                    table = self._try_parse_aligned_group(current_group, page_number)
                    if table:
                        tables.append(table)
                current_group = []
                continue
            
            # Count "columns" - words separated by 2+ spaces
            parts = re.split(r'\s{2,}', stripped)
            if len(parts) >= 3:
                current_group.append(stripped)
            elif current_group:
                # Line doesn't fit table pattern - end the group
                if len(current_group) >= 3:
                    table = self._try_parse_aligned_group(current_group, page_number)
                    if table:
                        tables.append(table)
                current_group = []

        # Check final group
        if len(current_group) >= 3:
            table = self._try_parse_aligned_group(current_group, page_number)
            if table:
                tables.append(table)

        return tables

    def _try_parse_aligned_group(self, lines: List[str], page_number: int) -> Optional[DetectedTable]:
        """Try to parse a group of aligned lines as a table."""
        parsed_rows = []
        
        for line in lines:
            cells = [c.strip() for c in re.split(r'\s{2,}', line) if c.strip()]
            if len(cells) >= 2:
                parsed_rows.append(cells)

        if len(parsed_rows) < 2:
            return None

        # Normalize column count
        max_cols = max(len(row) for row in parsed_rows)
        
        # Filter out rows with very different column counts (likely not part of table)
        mode_cols = max(set(len(row) for row in parsed_rows), 
                       key=lambda x: sum(1 for row in parsed_rows if len(row) == x))
        filtered = [row for row in parsed_rows if abs(len(row) - mode_cols) <= 1]
        
        if len(filtered) < 2:
            return None

        # Normalize
        normalized = []
        for row in filtered:
            while len(row) < mode_cols:
                row.append('')
            normalized.append(row[:mode_cols])

        # Determine header
        headers = normalized[0]
        rows = normalized[1:]
        
        if not self._is_likely_header(headers):
            if len(filtered) < 3 or mode_cols < 2:
                return None
            headers = [f"Column_{i+1}" for i in range(mode_cols)]
            rows = normalized

        return DetectedTable(
            headers=headers,
            rows=rows,
            page_number=page_number,
            confidence=0.6
        )

    def _process_raw_table(self, table_data: List[List], page_number: int) -> Optional[DetectedTable]:
        """Process raw table data (e.g., from pdfplumber)."""
        if not table_data or len(table_data) < 2:
            return None

        # Clean cells
        cleaned = []
        for row in table_data:
            cleaned_row = [self._clean_cell(str(cell) if cell is not None else '') for cell in row]
            cleaned.append(cleaned_row)

        # Determine headers
        headers = cleaned[0]
        rows = cleaned[1:]

        if not self._is_likely_header(headers):
            headers = [f"Column_{i+1}" for i in range(len(cleaned[0]))]
            rows = cleaned

        return DetectedTable(
            headers=headers,
            rows=rows,
            page_number=page_number,
            confidence=0.85
        )

    def _clean_cell(self, text: str) -> str:
        """Clean cell text - normalize whitespace."""
        return re.sub(r'\s+', ' ', text).strip()

    def _is_likely_header(self, row: List[str]) -> bool:
        """Heuristic to determine if a row is likely a genuine table header row.
        
        Headers tend to be:
        - Short meaningful text
        - Non-numeric
        - Title case or uppercase
        - Contain column words like 'Name', 'No', 'Date', etc.
        - Must NOT be single-letter OCR noise, isolated digits, or form field labels.
        """
        if not row:
            return False

        non_empty = [c.strip() for c in row if c and c.strip()]
        if len(non_empty) < 2:
            return False

        # Form / Card field labels are NOT table headers
        for c in non_empty:
            if re.search(r'(?:निर्वाचक|मतदाता|सदस्य)?\s*का?\s*नाम\s*[:\-\=]', c, re.IGNORECASE):
                return False
            if re.search(r'(?:पिता|पति|माता)\s*का\s*नाम\s*[:\-\=]', c, re.IGNORECASE):
                return False

        # Reject rows that are purely numbers or isolated punctuation fragments (like '6', '679', '_', '4:', '/')
        valid_words = 0
        for c in non_empty:
            # Pure numbers or punctuation
            if re.match(r'^[\d\s\W_]+$', c):
                continue
            # Tiny 1-2 char fragments (unless Devanagari)
            if len(c) <= 2 and not re.search(r'[\u0900-\u097F]', c):
                continue
            valid_words += 1

        if valid_words < 2:
            return False

        header_keywords = {
            'name', 'no', 'number', 'date', 'phone', 'email', 'class',
            'section', 'roll', 'id', 'gender', 'age', 'address', 'city',
            'status', 'type', 'department', 'dept', 'grade', 'marks',
            'score', 'total', 'rank', 'father', 'mother', 'dob',
            's.no', 'sr', 'serial', 'sl', 'remark', 'remarks',
            'mobile', 'contact', 'district', 'state', 'page',
            'नाम', 'क्रमांक', 'अनुक्रमांक', 'पिता', 'माता', 'पता', 'ग्राम',
            'उम्र', 'आयु', 'लिंग', 'वर्ग', 'श्रेणी', 'विषय', 'प्राप्तांक',
            'पूर्णांक', 'खाता', 'सदस्यता'
        }

        score = 0
        has_keyword = False
        for cell in non_empty:
            cell_lower = cell.lower().strip()
            # Long cells are unlikely headers
            if len(cell) > 50:
                return False
            
            # Numeric cells decrease score
            if re.match(r'^\d+\.?\d*$', cell_lower):
                score -= 1
            else:
                score += 1
            
            # Header keywords boost score
            for keyword in header_keywords:
                if keyword in cell_lower:
                    score += 2
                    has_keyword = True
                    break
            
            # Title case or uppercase text
            if cell.istitle() or cell.isupper():
                score += 1

        # Must either contain a recognized keyword, or have a strong score
        if not has_keyword and score < len(non_empty) * 1.0:
            return False

        return score > len(non_empty) * 0.5
