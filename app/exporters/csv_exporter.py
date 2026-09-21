import csv
import os
from typing import List, Dict
from app.exporters.base_exporter import BaseExporter
from app.database.models import Record, Category

class CSVExporter(BaseExporter):
    """CSV export."""
    
    def export_records(self, records: List[Record], output_path: str, document_name: str, categories: Dict[int, Category]):
        fields = self._get_field_names(records)
        display_headers = [self._get_display_field_name(f) for f in fields] + ['Category', 'Source Page']
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(display_headers)
            
            for record in records:
                values = self._get_record_values(record, fields)
                cat = categories.get(record.category_id)
                values.append(cat.name if cat else "")
                page_val = record.page_number if hasattr(record, 'page_number') and record.page_number else (getattr(record, 'source_page', '') or '')
                values.append(str(page_val))
                
                writer.writerow(values)
