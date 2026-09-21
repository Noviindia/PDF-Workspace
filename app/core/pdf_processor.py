"""
PDF Workspace - PDF Processor
Main orchestrator for PDF processing pipeline.
Uses pypdf for Android compatibility, with fitz fallback for desktop.
"""

import os
import threading
from typing import Callable, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass

from app.core.text_extractor import TextExtractor
from app.core.ocr_engine import OCREngine
from app.core.table_detector import TableDetector
from app.core.category_detector import CategoryDetector
from app.core.record_extractor import RecordExtractor
from app.core.search_engine import SearchEngine
from app.database.models import PageType


class ProcessingStatus(Enum):
    """Status of the PDF processing pipeline."""
    IDLE = "IDLE"
    READING = "READING"
    DETECTING_PAGES = "DETECTING_PAGES"
    EXTRACTING_TEXT = "EXTRACTING_TEXT"
    DETECTING_TABLES = "DETECTING_TABLES"
    DETECTING_SECTIONS = "DETECTING_SECTIONS"
    BUILDING_INDEX = "BUILDING_INDEX"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


@dataclass
class ProcessingProgress:
    """Progress data for the processing pipeline."""
    status: ProcessingStatus
    current_page: int
    total_pages: int
    message: str
    percentage: float


class PDFProcessor:
    """Orchestrates the complete PDF processing pipeline.
    
    Pipeline:
    1. Open and validate PDF
    2. For each page: detect type → extract text → detect tables → extract records
    3. Detect categories across all pages
    4. Build search index
    
    Works completely offline. All processing happens locally.
    """

    def __init__(self, db_repository):
        """Initialize with database repository.
        
        Args:
            db_repository: Repository instance for database operations.
        """
        self.db = db_repository
        self._is_cancelled = threading.Event()
        self.text_extractor = TextExtractor()
        self.ocr_engine = OCREngine()
        self.table_detector = TableDetector()
        self.category_detector = CategoryDetector()
        self.record_extractor = RecordExtractor()
        self.search_engine = SearchEngine(self.db)
        self._failed_pages: List[int] = []

    def process_pdf(self, file_path: str, 
                    progress_callback: Optional[Callable] = None,
                    ocr_language: str = 'eng+hin',
                    layout_mode: str = 'auto',
                    force_ocr: bool = False,
                    ocr_engine: str = 'auto') -> int:
        """Process a PDF file through the complete pipeline.
        
        Args:
            file_path: Path to the PDF file.
            progress_callback: Optional callable that receives ProcessingProgress.
            ocr_language: OCR language code(s), e.g. 'eng+hin', 'eng', 'hin'.
            layout_mode: 'auto', 'voter_list', 'table', or 'form'.
            force_ocr: If True, always runs OCR on all pages even if native text exists.
            
        Returns:
            Document ID on success, -1 on failure.
        """
        self._is_cancelled.clear()
        self._failed_pages = []

        if not os.path.exists(file_path):
            self._report_progress(progress_callback, ProcessingStatus.ERROR,
                                  0, 0, f"File not found: {file_path}", 0)
            return -1

        if not file_path.lower().endswith('.pdf'):
            self._report_progress(progress_callback, ProcessingStatus.ERROR,
                                  0, 0, "Not a PDF file", 0)
            return -1

        # Step 1: Read PDF metadata
        self._report_progress(progress_callback, ProcessingStatus.READING,
                              0, 0, "Reading PDF...", 5)

        total_pages = self.text_extractor.get_page_count(file_path)
        if total_pages == 0:
            self._report_progress(progress_callback, ProcessingStatus.ERROR,
                                  0, 0, "Could not read PDF or PDF is empty", 0)
            return -1

        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # Step 2: Detect pages
        self._report_progress(progress_callback, ProcessingStatus.DETECTING_PAGES,
                              0, total_pages, "Detecting pages...", 10)

        try:
            # Create Document record
            from datetime import datetime
            now = datetime.now().isoformat()
            doc = self.db.add_document(
                name=filename,
                file_path=file_path,
                page_count=total_pages,
                doc_type=PageType.NATIVE_TEXT,
                file_size=file_size
            )
            # doc might be a Document object or an int (id)
            document_id = doc.id if hasattr(doc, 'id') else doc
        except Exception as e:
            self._report_progress(progress_callback, ProcessingStatus.ERROR,
                                  0, total_pages, f"Database error: {str(e)}", 0)
            return -1

        all_pages_text: List[Tuple[int, str]] = []
        all_text_blocks: List[list] = []
        all_tables = []

        # Step 3: Process each page
        for page_num in range(total_pages):
            if self._is_cancelled.is_set():
                self._report_progress(progress_callback, ProcessingStatus.CANCELLED,
                                      page_num, total_pages, "Processing cancelled", 
                                      (page_num / total_pages) * 100)
                return document_id

            page_display = page_num + 1
            pct_base = 15
            pct_range = 60  # 15% to 75%
            pct = pct_base + (page_num / total_pages) * pct_range

            # Extract text
            self._report_progress(progress_callback, ProcessingStatus.EXTRACTING_TEXT,
                                  page_display, total_pages,
                                  f"Processing page {page_display} / {total_pages}", pct)

            try:
                # Check if page has text (native text PDF)
                text = ""
                blocks = []
                if not force_ocr:
                    text = self.text_extractor.extract_text_from_file(file_path, page_num)
                    blocks = self.text_extractor.extract_blocks_from_file(file_path, page_num)
                page_type = PageType.NATIVE_TEXT

                # If force_ocr requested, or text is empty/very short (< 30 chars), run OCR
                if (force_ocr or not text or len(text.strip()) < 30) and self.ocr_engine.is_available():
                    ocr_result = self.ocr_engine.ocr_page_from_file(file_path, page_num, language=ocr_language, engine_type=ocr_engine)
                    if ocr_result and ocr_result.text.strip():
                        if force_ocr or len(ocr_result.text.strip()) > len(text.strip()):
                            page_type = PageType.SCANNED
                            text = ocr_result.text
                            # Convert OCR blocks to TextBlock format so bounding boxes are stored
                            if ocr_result.blocks:
                                from app.core.text_extractor import TextBlock
                                ocr_text_blocks = []
                                for ob in ocr_result.blocks:
                                    b_type = 'word' if len(ob.text.split()) == 1 else 'text'
                                    ocr_text_blocks.append(TextBlock(
                                        text=ob.text,
                                        x0=ob.x0, y0=ob.y0, x1=ob.x1, y1=ob.y1,
                                        font_size=12.0, font_name="OCR",
                                        is_bold=False, is_italic=False,
                                        block_type=b_type
                                    ))
                                blocks = ocr_text_blocks
                elif not text.strip():
                    page_type = PageType.SCANNED  # Scanned but no OCR available

                # Get page dimensions
                width, height = self.text_extractor.get_page_dimensions(file_path, page_num)

                # Determine if page is a Voter List / Electoral Roll card layout
                is_voter_page = (layout_mode == 'voter_list') or (layout_mode == 'auto' and self.record_extractor.is_voter_list_content(text))

                page_tables = []
                if not is_voter_page or layout_mode == 'table':
                    # Detect tables on this page (only for tabular documents)
                    self._report_progress(progress_callback, ProcessingStatus.DETECTING_TABLES,
                                          page_display, total_pages,
                                          f"Detecting tables page {page_display}", pct + 2)

                    page_tables = self.table_detector.detect_tables_from_file(file_path, page_display)
                    if not page_tables:
                        page_tables = self.table_detector.detect_tables_from_text(text, page_display)
                    all_tables.extend(page_tables)

                # Store page in database
                ocr_conf = None
                if page_type == PageType.SCANNED and hasattr(self.ocr_engine, '_last_confidence'):
                    ocr_conf = self.ocr_engine._last_confidence

                page_obj = self.db.add_page(
                    document_id=document_id,
                    page_number=page_display,
                    raw_text=text,
                    processed_text=text,
                    page_type=page_type,
                    ocr_confidence=ocr_conf,
                    width=width,
                    height=height,
                    has_tables=len(page_tables) > 0
                )
                page_id = page_obj.id if hasattr(page_obj, 'id') else None

                # Store detected tables in database
                if page_id:
                    for pt in page_tables:
                        try:
                            self.db.add_table_data(
                                page_id=page_id,
                                document_id=document_id,
                                page_number=page_display,
                                headers=pt.headers,
                                rows=pt.rows,
                                bbox=pt.bbox
                            )
                        except Exception as e:
                            print(f"Error storing table data: {e}")

                # Store bounding boxes if available
                if page_id:
                    for block in blocks:
                        if hasattr(block, 'text') and block.text.strip():
                            try:
                                self.db.add_bounding_box(
                                    page_id=page_id,
                                    text=block.text,
                                    x0=block.x0, y0=block.y0,
                                    x1=block.x1, y1=block.y1,
                                    block_type=block.block_type
                                )
                            except Exception:
                                pass  # Non-critical

                # Extract records
                if is_voter_page and layout_mode != 'table':
                    # Multi-card / Electoral roll extraction
                    voter_records = self.record_extractor.extract_voter_cards(text, page_display, blocks=blocks)
                    for record in voter_records:
                        try:
                            self.db.add_record(
                                document_id=document_id,
                                page_number=page_display,
                                category_id=None,
                                data=record.data,
                                source_text=record.source_text,
                                bbox_x=record.bbox[0] if record.bbox else 0,
                                bbox_y=record.bbox[1] if record.bbox else 0,
                                bbox_w=record.bbox[2] if record.bbox else 0,
                                bbox_h=record.bbox[3] if record.bbox else 0
                            )
                        except Exception as e:
                            print(f"Error adding voter record: {e}")
                else:
                    # Extract records from tables
                    for table in page_tables:
                        records = self.record_extractor.extract_from_tables([table], page_display)
                        for record in records:
                            try:
                                self.db.add_record(
                                    document_id=document_id,
                                    page_number=page_display,
                                    category_id=None,
                                    data=record.data,
                                    source_text=record.source_text,
                                    bbox_x=record.bbox[0] if record.bbox else 0,
                                    bbox_y=record.bbox[1] if record.bbox else 0,
                                    bbox_w=record.bbox[2] if record.bbox else 0,
                                    bbox_h=record.bbox[3] if record.bbox else 0
                                )
                            except Exception as e:
                                print(f"Error adding record: {e}")

                    # Extract records from text key-value pairs
                    text_records = self.record_extractor.extract_from_text(text, page_display)
                    for record in text_records:
                        try:
                            self.db.add_record(
                                document_id=document_id,
                                page_number=page_display,
                                category_id=None,
                                data=record.data,
                                source_text=record.source_text,
                                bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0
                            )
                        except Exception as e:
                            print(f"Error adding text record: {e}")

                all_pages_text.append((page_display, text))
                all_text_blocks.append(blocks if blocks else [])

            except Exception as e:
                print(f"Error processing page {page_display}: {e}")
                self._failed_pages.append(page_display)
                all_pages_text.append((page_display, ""))
                all_text_blocks.append([])
                continue  # Don't crash on single page failure

        if self._is_cancelled.is_set():
            return document_id

        # Step 4: Detect categories
        self._report_progress(progress_callback, ProcessingStatus.DETECTING_SECTIONS,
                              total_pages, total_pages, "Detecting categories...", 80)

        try:
            # Convert TextBlock objects to dicts for category detector
            text_blocks_as_dicts = []
            for page_blocks in all_text_blocks:
                block_dicts = []
                for b in page_blocks:
                    if hasattr(b, 'text'):
                        block_dicts.append({
                            'text': b.text,
                            'x0': b.x0, 'y0': b.y0,
                            'x1': b.x1, 'y1': b.y1,
                            'font_size': b.font_size,
                            'font_name': b.font_name,
                            'is_bold': b.is_bold,
                            'block_type': b.block_type
                        })
                text_blocks_as_dicts.append(block_dicts)

            categories = self.category_detector.detect_categories(
                all_pages_text, text_blocks_as_dicts
            )

            category_map = {}  # name -> category_id
            for cat in categories:
                try:
                    cat_obj = self.db.add_category(
                        document_id=document_id,
                        name=cat.name,
                        parent_id=None
                    )
                    cat_id = cat_obj.id if hasattr(cat_obj, 'id') else cat_obj
                    category_map[cat.name] = cat_id
                except Exception as e:
                    print(f"Error adding category {cat.name}: {e}")

            # Assign records to categories based on detection
            if category_map:
                self._assign_records_to_categories(document_id, categories, category_map)

            # Update category counts
            try:
                self.db.update_category_counts(document_id)
            except Exception:
                pass

        except Exception as e:
            print(f"Category detection error: {e}")

        # Step 5: Build search index
        self._report_progress(progress_callback, ProcessingStatus.BUILDING_INDEX,
                              total_pages, total_pages, "Building search index...", 90)

        try:
            self.search_engine.build_index(document_id)
        except Exception as e:
            print(f"Search index error: {e}")

        # Complete
        try:
            self.db.set_meta('document_status', 'READY')
        except Exception:
            pass

        success_pages = total_pages - len(self._failed_pages)
        msg = f"Complete - {success_pages}/{total_pages} pages processed"
        if self._failed_pages:
            msg += f" ({len(self._failed_pages)} failed)"

        self._report_progress(progress_callback, ProcessingStatus.COMPLETE,
                              total_pages, total_pages, msg, 100)

        return document_id

    def _assign_records_to_categories(self, document_id: int, 
                                       categories: list, 
                                       category_map: dict):
        """Assign records to detected categories based on page numbers and content."""
        try:
            records = self.db.get_records_by_document(document_id)
            for record in records:
                record_id = record.id if hasattr(record, 'id') else None
                if not record_id:
                    continue

                record_page = record.page_number if hasattr(record, 'page_number') else 0
                record_data = record.data if hasattr(record, 'data') else {}

                # Try to match by page number
                for cat in categories:
                    if record_page in cat.page_numbers:
                        cat_id = category_map.get(cat.name)
                        if cat_id:
                            try:
                                self.db.update_record(record_id, category_id=cat_id)
                            except Exception:
                                pass
                            break

                    # Also check if record data contains category hint
                    if isinstance(record_data, dict):
                        for val in record_data.values():
                            if isinstance(val, str) and cat.name.lower() in val.lower():
                                cat_id = category_map.get(cat.name)
                                if cat_id:
                                    try:
                                        self.db.update_record(record_id, category_id=cat_id)
                                    except Exception:
                                        pass
                                    break
        except Exception as e:
            print(f"Error assigning categories: {e}")

    def _report_progress(self, callback: Optional[Callable], 
                         status: ProcessingStatus,
                         current_page: int, total_pages: int,
                         message: str, percentage: float):
        """Report processing progress to callback."""
        if callback:
            try:
                progress = ProcessingProgress(
                    status=status,
                    current_page=current_page,
                    total_pages=total_pages,
                    message=message,
                    percentage=min(percentage, 100.0)
                )
                callback(progress)
            except Exception as e:
                print(f"Progress callback error: {e}")

    def cancel(self):
        """Cancel ongoing processing."""
        self._is_cancelled.set()

    @property
    def failed_pages(self) -> List[int]:
        """Get list of page numbers that failed processing."""
        return self._failed_pages.copy()
