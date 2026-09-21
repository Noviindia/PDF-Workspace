import os
from typing import List, Dict
from app.exporters.base_exporter import BaseExporter
from app.database.models import Record, Category

class TXTExporter(BaseExporter):
    """Plain text export."""
    
    def export_records(self, records: List[Record], output_path: str, document_name: str, categories: Dict[int, Category]):
        fields = self._get_field_names(records)
        headers = fields + ['Category', 'Source Page']
        
        category_records = {}
        for record in records:
            cat_id = record.category_id
            if cat_id not in category_records:
                category_records[cat_id] = []
            category_records[cat_id].append(record)
            
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"{document_name}\n")
            f.write(f"{'=' * len(document_name)}\n\n")
            
            f.write(f"Summary: {len(records)} records across {len(category_records)} categories.\n\n")
            
            for cat_id, cat_recs in category_records.items():
                cat = categories.get(cat_id)
                cat_name = cat.name if cat else "Uncategorized"
                
                f.write(f"{cat_name} ({len(cat_recs)} records)\n")
                f.write(f"{'-' * (len(cat_name) + len(str(len(cat_recs))) + 11)}\n\n")
                
                # Determine column widths
                col_widths = [len(h) for h in headers]
                all_rows = []
                for record in cat_recs:
                    values = self._get_record_values(record, fields)
                    values.append(cat_name)
                    values.append(str(record.source_page) if record.source_page else "")
                    all_rows.append(values)
                    
                    for i, val in enumerate(values):
                        if len(str(val)) > col_widths[i]:
                            col_widths[i] = len(str(val))
                            
                # Write header
                header_format = " | ".join([f"{{:<{w}}}" for w in col_widths])
                f.write(header_format.format(*headers) + "\n")
                
                # Write separator
                sep = "-+-".join(["-" * w for w in col_widths])
                f.write(sep + "\n")
                
                # Write rows
                for row in all_rows:
                    f.write(header_format.format(*[str(v) for v in row]) + "\n")
                    
                f.write("\n\n")
