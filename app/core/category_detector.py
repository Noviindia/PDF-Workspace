import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict, Counter

@dataclass
class DetectedCategory:
    name: str
    record_indices: List[int]
    page_numbers: List[int]
    confidence: float
    parent_name: Optional[str] = None

class CategoryDetector:
    def detect_categories(self, pages_text, text_blocks: Optional[List[List[dict]]] = None) -> List[DetectedCategory]:
        """Main method that tries multiple strategies for category detection."""
        if isinstance(pages_text, str):
            pages_text = [(1, pages_text)]
        if text_blocks is None:
            text_blocks = [[] for _ in pages_text]

        categories = []
        
        # Strategy 2: Pattern-based
        categories.extend(self._detect_patterns(pages_text))

        # Strategy 3: Text heading heuristics
        categories.extend(self._detect_text_headings(pages_text))
        
        # Strategy 1: Heading-based (from PDF block sizes)
        headings = self._detect_headings(text_blocks)
        for heading, page_num in headings:
            categories.append(DetectedCategory(
                name=heading,
                record_indices=[],
                page_numbers=[page_num],
                confidence=0.7
            ))
            
        return self._merge_similar_categories(categories)

    def _detect_text_headings(self, pages_text: List[Tuple[int, str]]) -> List[DetectedCategory]:
        """Detect headings from short capitalized text lines."""
        categories = []
        heading_keywords = ['report', 'summary', 'distribution', 'details', 'list', 'roster', 'records', 'schedule']
        for page_num, text in pages_text:
            for line in text.split('\n'):
                line_str = line.strip()
                if 4 < len(line_str) < 50:
                    if (line_str.istitle() or line_str.isupper()) and any(k in line_str.lower() for k in heading_keywords):
                        categories.append(DetectedCategory(
                            name=line_str,
                            record_indices=[],
                            page_numbers=[page_num],
                            confidence=0.75
                        ))
        return categories

    def _detect_headings(self, text_blocks: List[List[dict]]) -> List[Tuple[str, int]]:
        """Find heading text and page numbers."""
        headings = []
        for i, blocks in enumerate(text_blocks):
            page_num = i + 1
            for block in blocks:
                if block.get("type") == 0:  # text
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get("size", 10) > 14:  # Heading heuristic
                                text = span.get("text", "").strip()
                                if text and len(text) < 100:
                                    headings.append((text, page_num))
        return headings

    def _detect_patterns(self, pages_text: List[Tuple[int, str]]) -> List[DetectedCategory]:
        """Regex-based pattern matching."""
        categories = []
        patterns = self._get_common_patterns()
        
        for page_num, text in pages_text:
            for pattern_name, pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    cat_name = match.group(0).strip()
                    categories.append(DetectedCategory(
                        name=cat_name,
                        record_indices=[],
                        page_numbers=[page_num],
                        confidence=0.8
                    ))
        return categories

    def _detect_from_table_columns(self, headers: List[str], rows: List[List[str]], page_number: int) -> List[DetectedCategory]:
        """Look at column headers for categories."""
        categories = []
        target_cols = ['class', 'section', 'department', 'category', 'type', 'status']
        
        for idx, header in enumerate(headers):
            if any(target in header.lower() for target in target_cols):
                values = [row[idx] for row in rows if idx < len(row)]
                unique_values = set(values)
                for val in unique_values:
                    if val.strip():
                        categories.append(DetectedCategory(
                            name=f"{header}: {val.strip()}",
                            record_indices=[],
                            page_numbers=[page_number],
                            confidence=0.9
                        ))
        return categories

    def _merge_similar_categories(self, categories: List[DetectedCategory]) -> List[DetectedCategory]:
        """Merge duplicates."""
        merged = {}
        for cat in categories:
            key = cat.name.lower()
            if key not in merged:
                merged[key] = cat
            else:
                existing = merged[key]
                existing.page_numbers = list(set(existing.page_numbers + cat.page_numbers))
                existing.confidence = max(existing.confidence, cat.confidence)
        return list(merged.values())

    def _get_common_patterns(self) -> List[Tuple[str, str]]:
        """Returns regex patterns for common category types."""
        return [
            ('ClassSection', r'Class\s*\d+\s*[-–]\s*Section\s*[A-Za-z0-9]+'),
            ('Class', r'Class\s*\d+'),
            ('Grade', r'Grade\s*\d+'),
            ('Section', r'Section\s*[A-Za-z0-9]+'),
            ('Department', r'Department\s*[:of]*\s*([A-Za-z\s]+)'),
        ]

