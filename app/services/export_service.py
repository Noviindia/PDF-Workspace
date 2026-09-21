import os
from typing import Optional, List, Dict
from app.database.models import ExportConfig
from app.database.repository import Repository

class ExportService:
    """
    Export orchestration service.
    """

    def __init__(self, repository: Repository):
        """
        Initialize the export service.
        
        Args:
            repository (Repository): The database repository.
        """
        self._repository = repository
        self._exporters = {}

    def export(self, config: ExportConfig) -> str:
        """
        Export data based on the provided configuration.
        
        Args:
            config (ExportConfig): The export configuration.
            
        Returns:
            str: The output file path.
            
        Raises:
            ValueError: If the export fails or the format is not supported.
        """
        try:
            exporter = self._get_exporter(config.format)
            if not exporter:
                raise ValueError(f"Unsupported export format: {config.format}")
                
            return exporter.export(config)
        except Exception as e:
            raise ValueError(f"Export failed: {str(e)}")

    def _get_exporter(self, format_name: str):
        """
        Get or create the appropriate exporter.
        
        Args:
            format_name (str): The format name.
            
        Returns:
            Exporter instance or None if unsupported.
        """
        if format_name in self._exporters:
            return self._exporters[format_name]
            
        exporter = None
        if format_name == 'xlsx':
            from app.exporters.xlsx_exporter import XLSXExporter
            exporter = XLSXExporter(self._repository)
        elif format_name == 'docx':
            from app.exporters.docx_exporter import DOCXExporter
            exporter = DOCXExporter(self._repository)
        elif format_name == 'csv':
            from app.exporters.csv_exporter import CSVExporter
            exporter = CSVExporter(self._repository)
        elif format_name == 'json':
            from app.exporters.json_exporter import JSONExporter
            exporter = JSONExporter(self._repository)
        elif format_name == 'html':
            from app.exporters.html_exporter import HTMLExporter
            exporter = HTMLExporter(self._repository)
        elif format_name == 'txt':
            from app.exporters.txt_exporter import TXTExporter
            exporter = TXTExporter(self._repository)
        elif format_name in ('md', 'markdown'):
            from app.exporters.markdown_exporter import MarkdownExporter
            exporter = MarkdownExporter(self._repository)
            
        if exporter:
            self._exporters[format_name] = exporter
            
        return exporter

    def get_available_formats(self) -> List[Dict]:
        """
        Get a list of available export formats.
        
        Returns:
            List[Dict]: The list of available formats.
        """
        return [
            {'id': 'xlsx', 'name': 'Excel Spreadsheet', 'extension': '.xlsx', 'description': 'Structured spreadsheet with multiple sheets'},
            {'id': 'docx', 'name': 'Word Document', 'extension': '.docx', 'description': 'Formatted document with tables'},
            {'id': 'csv', 'name': 'CSV File', 'extension': '.csv', 'description': 'Comma-separated values'},
            {'id': 'json', 'name': 'JSON File', 'extension': '.json', 'description': 'Structured JSON data'},
            {'id': 'html', 'name': 'HTML Page', 'extension': '.html', 'description': 'Styled web page'},
            {'id': 'txt', 'name': 'Plain Text', 'extension': '.txt', 'description': 'Simple text format'},
            {'id': 'md', 'name': 'Markdown', 'extension': '.md', 'description': 'Markdown with tables'},
        ]

    def get_export_scopes(self, document_id: int) -> List[Dict]:
        """
        Get available export scopes with their respective counts.
        
        Args:
            document_id (int): The ID of the document.
            
        Returns:
            List[Dict]: The list of available scopes.
        """
        total_records = len(self._repository.get_all_records(document_id))
        
        categories = self._repository.get_categories(document_id)
        category_list = []
        for cat in categories:
            count = len(self._repository.get_records_by_category(cat.id))
            category_list.append({'name': cat.name, 'count': count})
            
        return [
            {'id': 'all', 'name': 'Entire Document', 'count': total_records},
            {'id': 'category', 'name': 'By Category', 'categories': category_list},
            {'id': 'selected', 'name': 'Selected Records', 'count': 0},
            {'id': 'search', 'name': 'Search Results', 'count': 0},
        ]
