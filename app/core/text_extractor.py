"""
PDF Workspace - Text Extractor
Extracts text from PDF pages using pypdf (pure Python, Android-compatible).
Falls back to pdfplumber for enhanced extraction if available.
"""

from typing import List, Optional
from dataclasses import dataclass

# Try multiple PDF libraries for maximum compatibility
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# Optional: PyMuPDF for desktop development
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


@dataclass
class TextBlock:
    """Represents a block of text with position and style information."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float
    font_name: str
    is_bold: bool
    is_italic: bool
    block_type: str  # 'text', 'heading', 'footer'


class TextExtractor:
    """Extract text from PDF files using available libraries.
    
    Supports multiple backends:
    - PyMuPDF (fitz) - fastest, desktop only
    - pypdf - pure Python, works on Android
    - pdfplumber - pure Python, better table/position support
    """

    def __init__(self, file_path: Optional[str] = None):
        """Initialize with best available backend."""
        self.file_path = file_path
        if HAS_FITZ:
            self._backend = 'fitz'
        elif HAS_PDFPLUMBER:
            self._backend = 'pdfplumber'
        elif HAS_PYPDF:
            self._backend = 'pypdf'
        else:
            self._backend = 'none'

    @property
    def backend_name(self) -> str:
        """Return name of active PDF backend."""
        return self._backend

    def extract_text(self, page_number: int = 0, file_path: Optional[str] = None) -> str:
        """Convenience wrapper for extract_text_from_file."""
        path = file_path or self.file_path
        if not path:
            return ""
        return self.extract_text_from_file(path, page_number)

    def extract_blocks(self, page_number: int = 0, file_path: Optional[str] = None) -> List[TextBlock]:
        """Convenience wrapper for extract_blocks_from_file."""
        path = file_path or self.file_path
        if not path:
            return []
        return self.extract_blocks_from_file(path, page_number)

    def extract_text_from_file(self, file_path: str, page_number: int) -> str:
        """Extract text from a specific page of a PDF file.
        
        Args:
            file_path: Path to the PDF file.
            page_number: Zero-based page index.
            
        Returns:
            Extracted text string.
        """
        try:
            if self._backend == 'fitz':
                return self._extract_fitz(file_path, page_number)
            elif self._backend == 'pdfplumber':
                return self._extract_pdfplumber(file_path, page_number)
            elif self._backend == 'pypdf':
                return self._extract_pypdf(file_path, page_number)
            else:
                return ""
        except Exception as e:
            print(f"Text extraction error on page {page_number}: {e}")
            return ""

    def extract_blocks_from_file(self, file_path: str, page_number: int) -> List[TextBlock]:
        """Extract structured text blocks with positions from a page.
        
        Args:
            file_path: Path to the PDF file.
            page_number: Zero-based page index.
            
        Returns:
            List of TextBlock objects with position and style data.
        """
        try:
            if self._backend == 'fitz':
                return self._extract_blocks_fitz(file_path, page_number)
            elif self._backend == 'pdfplumber':
                return self._extract_blocks_pdfplumber(file_path, page_number)
            elif self._backend == 'pypdf':
                return self._extract_blocks_pypdf(file_path, page_number)
            else:
                return []
        except Exception as e:
            print(f"Block extraction error on page {page_number}: {e}")
            return []

    def has_text(self, *args, **kwargs) -> bool:
        """Check if a page has extractable text."""
        if len(args) == 2:
            file_path, page_number = args[0], args[1]
        elif len(args) == 1:
            file_path = self.file_path
            page_number = args[0]
        else:
            file_path = kwargs.get('file_path') or self.file_path
            page_number = kwargs.get('page_number', 0)
        if not file_path:
            return False
        text = self.extract_text_from_file(file_path, page_number)
        return len(text.strip()) > 10

    def get_page_count(self, file_path: Optional[str] = None) -> int:
        """Get total page count of a PDF."""
        path = file_path or self.file_path
        if not path:
            return 0
        try:
            if self._backend == 'fitz':
                doc = fitz.open(path)
                count = len(doc)
                doc.close()
                return count
            elif self._backend == 'pdfplumber':
                with pdfplumber.open(path) as pdf:
                    return len(pdf.pages)
            elif self._backend == 'pypdf':
                reader = pypdf.PdfReader(path)
                return len(reader.pages)
        except Exception as e:
            print(f"Error getting page count: {e}")
        return 0

    def get_page_dimensions(self, *args, **kwargs) -> tuple:
        """Get page width and height."""
        if len(args) == 2:
            if isinstance(args[0], str):
                file_path, page_number = args[0], args[1]
            else:
                page_number, file_path = args[0], args[1]
        elif len(args) == 1:
            if isinstance(args[0], str):
                file_path, page_number = args[0], 0
            else:
                page_number = args[0]
                file_path = kwargs.get('file_path') or self.file_path
        else:
            file_path = kwargs.get('file_path') or self.file_path
            page_number = kwargs.get('page_number', 0)

        if not file_path:
            return (612.0, 792.0)
        try:
            if self._backend == 'fitz':
                doc = fitz.open(file_path)
                page = doc.load_page(page_number)
                rect = page.rect
                w, h = rect.width, rect.height
                doc.close()
                return (w, h)
            elif self._backend == 'pypdf':
                reader = pypdf.PdfReader(file_path)
                page = reader.pages[page_number]
                box = page.mediabox
                return (float(box.width), float(box.height))
            elif self._backend == 'pdfplumber':
                with pdfplumber.open(file_path) as pdf:
                    page = pdf.pages[page_number]
                    return (page.width, page.height)
        except Exception:
            pass
        return (612.0, 792.0)

    def get_text_percentage(self, file_path: str, page_number: int) -> float:
        """Estimate how much of the page contains text vs images."""
        text = self.extract_text_from_file(file_path, page_number)
        if len(text.strip()) > 100:
            return 0.8
        elif len(text.strip()) > 10:
            return 0.3
        return 0.0

    # --- PyMuPDF (fitz) backend ---

    def _extract_fitz(self, file_path: str, page_number: int) -> str:
        """Extract text using PyMuPDF."""
        doc = fitz.open(file_path)
        try:
            page = doc.load_page(page_number)
            return page.get_text()
        finally:
            doc.close()

    def _extract_blocks_fitz(self, file_path: str, page_number: int) -> List[TextBlock]:
        """Extract blocks using PyMuPDF with full position data."""
        doc = fitz.open(file_path)
        blocks = []
        try:
            page = doc.load_page(page_number)
            page_dict = page.get_text("dict")
            page_height = page_dict.get("height", 792)

            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:  # text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text:
                                bbox = span.get("bbox", [0, 0, 0, 0])
                                font_size = span.get("size", 10)
                                font_name = span.get("font", "Unknown")
                                blocks.append(TextBlock(
                                    text=text,
                                    x0=bbox[0], y0=bbox[1],
                                    x1=bbox[2], y1=bbox[3],
                                    font_size=font_size,
                                    font_name=font_name,
                                    is_bold="Bold" in font_name or "bold" in font_name.lower(),
                                    is_italic="Italic" in font_name or "italic" in font_name.lower(),
                                    block_type=self._classify_block(bbox, font_size, page_height)
                                ))

            # Also extract word-level boxes for exact word highlighting
            try:
                raw_words = page.get_text("words")
                for w in raw_words:
                    if len(w) >= 5 and str(w[4]).strip():
                        blocks.append(TextBlock(
                            text=str(w[4]).strip(),
                            x0=float(w[0]), y0=float(w[1]),
                            x1=float(w[2]), y1=float(w[3]),
                            font_size=10.0,
                            font_name="Word",
                            is_bold=False,
                            is_italic=False,
                            block_type='word'
                        ))
            except Exception:
                pass
        finally:
            doc.close()
        return blocks

    # --- pypdf backend ---

    def _extract_pypdf(self, file_path: str, page_number: int) -> str:
        """Extract text using pypdf (pure Python)."""
        reader = pypdf.PdfReader(file_path)
        if page_number >= len(reader.pages):
            return ""
        page = reader.pages[page_number]
        return page.extract_text() or ""

    def _extract_blocks_pypdf(self, file_path: str, page_number: int) -> List[TextBlock]:
        """Extract blocks using pypdf - limited position data."""
        text = self._extract_pypdf(file_path, page_number)
        if not text:
            return []
        
        # pypdf doesn't provide detailed position data
        # Create blocks from paragraphs
        blocks = []
        lines = text.split('\n')
        y_pos = 50.0
        
        for line in lines:
            line = line.strip()
            if not line:
                y_pos += 15.0
                continue
            
            # Heuristic: detect headings by length and position
            is_heading = len(line) < 60 and y_pos < 100
            font_size = 16.0 if is_heading else 11.0
            
            blocks.append(TextBlock(
                text=line,
                x0=50.0, y0=y_pos,
                x1=550.0, y1=y_pos + font_size,
                font_size=font_size,
                font_name="Unknown",
                is_bold=is_heading,
                is_italic=False,
                block_type='heading' if is_heading else 'text'
            ))
            y_pos += font_size + 4.0
        
        return blocks

    # --- pdfplumber backend ---

    def _extract_pdfplumber(self, file_path: str, page_number: int) -> str:
        """Extract text using pdfplumber."""
        with pdfplumber.open(file_path) as pdf:
            if page_number >= len(pdf.pages):
                return ""
            page = pdf.pages[page_number]
            return page.extract_text() or ""

    def _extract_blocks_pdfplumber(self, file_path: str, page_number: int) -> List[TextBlock]:
        """Extract blocks using pdfplumber with position data."""
        blocks = []
        with pdfplumber.open(file_path) as pdf:
            if page_number >= len(pdf.pages):
                return blocks
            page = pdf.pages[page_number]
            words = page.extract_words() or []
            
            # Group words into lines by y-coordinate
            current_line_words = []
            current_y = None
            y_tolerance = 3.0
            
            for word in words:
                word_top = float(word.get('top', 0))
                if current_y is None or abs(word_top - current_y) > y_tolerance:
                    if current_line_words:
                        blocks.append(self._words_to_block(current_line_words, page.height))
                    current_line_words = [word]
                    current_y = word_top
                else:
                    current_line_words.append(word)
            
            if current_line_words:
                blocks.append(self._words_to_block(current_line_words, page.height))
        
        return blocks

    def _words_to_block(self, words: list, page_height: float) -> TextBlock:
        """Convert a group of pdfplumber words into a TextBlock."""
        text = " ".join(w.get('text', '') for w in words)
        x0 = min(float(w.get('x0', 0)) for w in words)
        y0 = min(float(w.get('top', 0)) for w in words)
        x1 = max(float(w.get('x1', 0)) for w in words)
        y1 = max(float(w.get('bottom', 0)) for w in words)
        font_size = float(words[0].get('size', 11)) if 'size' in words[0] else 11.0
        font_name = words[0].get('fontname', 'Unknown') if 'fontname' in words[0] else 'Unknown'
        
        return TextBlock(
            text=text,
            x0=x0, y0=y0, x1=x1, y1=y1,
            font_size=font_size,
            font_name=font_name,
            is_bold='Bold' in font_name or 'bold' in font_name.lower(),
            is_italic='Italic' in font_name or 'italic' in font_name.lower(),
            block_type=self._classify_block([x0, y0, x1, y1], font_size, page_height)
        )

    # --- Shared utilities ---

    def _classify_block(self, bbox, font_size: float, page_height: float) -> str:
        """Classify as 'heading', 'text', 'footer' based on font size and position."""
        if font_size > 14:
            return "heading"
        y1 = bbox[3] if isinstance(bbox, (list, tuple)) else bbox
        if y1 > page_height * 0.9:
            return "footer"
        return "text"
