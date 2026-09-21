import os
import shutil
import threading
from typing import Callable, Optional

from app.core.pdf_processor import PDFProcessor, ProcessingProgress, ProcessingStatus
from app.core.search_engine import SearchEngine
from app.database.db_manager import DatabaseManager
from app.database.repository import Repository


class ProcessingService:
    """
    Orchestration service for the PDF import pipeline.
    """

    def __init__(self, project_path: str):
        """
        Initialize the processing service and project directory structure.
        
        Args:
            project_path (str): The absolute path to the project directory.
        """
        self.project_path = project_path
        os.makedirs(self.project_path, exist_ok=True)
        
        self.source_dir = os.path.join(self.project_path, 'source')
        self.exports_dir = os.path.join(self.project_path, 'exports')
        os.makedirs(self.source_dir, exist_ok=True)
        os.makedirs(self.exports_dir, exist_ok=True)
        
        db_path = os.path.join(self.project_path, 'project.db')
        self._db_manager = DatabaseManager(db_path)
        self._db_manager.initialize()
        
        self._repository = Repository(self._db_manager)
        self._processor = PDFProcessor(self._repository)
        self._search_engine = SearchEngine(self._repository)
        self._processing_thread: Optional[threading.Thread] = None

    def import_pdf(self, file_path: str, progress_callback: Optional[Callable] = None, ocr_language: str = 'eng+hin', layout_mode: str = 'auto', force_ocr: bool = False, ocr_engine: str = 'auto') -> int:
        """
        Synchronously import and process a PDF file.
        
        Args:
            file_path (str): The path to the source PDF file.
            progress_callback (Callable, optional): Callback for progress updates.
            ocr_language (str, optional): Language code for OCR (e.g. 'eng+hin', 'eng', 'hin').
            layout_mode (str, optional): 'auto', 'voter_list', 'table', or 'form'.
            force_ocr (bool, optional): If True, forces OCR on all pages.
            ocr_engine (str, optional): 'lens' (Google Lens), 'tesseract' (Local), or 'auto'.
            
        Returns:
            int: The ID of the imported document.
            
        Raises:
            FileNotFoundError: If the input file does not exist.
            ValueError: If there is an issue during processing.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        filename = os.path.basename(file_path)
        dest_path = os.path.join(self.source_dir, filename)
        
        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            raise ValueError(f"Failed to copy file: {e}")
            
        return self._processor.process_pdf(dest_path, progress_callback, ocr_language=ocr_language, layout_mode=layout_mode, force_ocr=force_ocr, ocr_engine=ocr_engine)

    def import_pdf_async(
        self,
        file_path: str,
        progress_callback: Optional[Callable] = None,
        completion_callback: Optional[Callable] = None,
        ocr_language: str = 'eng+hin',
        layout_mode: str = 'auto',
        force_ocr: bool = False,
        ocr_engine: str = 'auto'
    ) -> None:
        """
        Asynchronously import and process a PDF file in a background thread.
        
        Args:
            file_path (str): The path to the source PDF file.
            progress_callback (Callable, optional): Callback for progress updates.
            completion_callback (Callable, optional): Callback executed when done, taking (doc_id, error_string).
            ocr_language (str, optional): Language code for OCR.
            layout_mode (str, optional): Document layout mode.
            force_ocr (bool, optional): If True, forces OCR on all pages.
            ocr_engine (str, optional): 'lens' (Google Lens), 'tesseract' (Local), or 'auto'.
        """
        def worker():
            try:
                doc_id = self.import_pdf(file_path, progress_callback, ocr_language=ocr_language, layout_mode=layout_mode, force_ocr=force_ocr, ocr_engine=ocr_engine)
                if completion_callback:
                    completion_callback(doc_id, None)
            except Exception as e:
                if completion_callback:
                    completion_callback(None, str(e))
                    
        self._processing_thread = threading.Thread(target=worker, daemon=True)
        self._processing_thread.start()

    def cancel_processing(self) -> None:
        """
        Cancel the ongoing processing operation.
        """
        self._processor.cancel()

    def get_repository(self) -> Repository:
        """
        Get the database repository instance.
        
        Returns:
            Repository: The repository instance.
        """
        return self._repository

    def get_search_engine(self) -> SearchEngine:
        """
        Get the search engine instance.
        
        Returns:
            SearchEngine: The search engine instance.
        """
        return self._search_engine

    def get_pdf_path(self, document_id: int = None) -> Optional[str]:
        """
        Get the path to the source PDF.
        
        Args:
            document_id (int, optional): The ID of the document to look up.
            
        Returns:
            str: The absolute path to the PDF file, or None if not found.
        """
        if document_id is not None:
            doc = self._repository.get_document(document_id)
            if doc:
                return doc.file_path
                
        # Otherwise find first PDF in source directory
        if os.path.exists(self.source_dir):
            for filename in os.listdir(self.source_dir):
                if filename.lower().endswith('.pdf'):
                    return os.path.join(self.source_dir, filename)
        return None

    def close(self) -> None:
        """
        Close the database connection.
        """
        self._db_manager.close()
