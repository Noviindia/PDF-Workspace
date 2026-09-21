import os
from typing import List, Dict
from app.exporters.base_exporter import BaseExporter
from app.database.models import Record, Category

class MarkdownExporter(BaseExporter):
    """Markdown export."""
    
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
            f.write(f"# {document_name}\n\n")
            
            f.write(f"## Summary\n")
            f.write(f"- **Total Records:** {len(records)}\n")
            f.write(f"- **Total Categories:** {len(category_records)}\n\n")
            
            f.write("## Table of Contents\n")
            for cat_id in category_records.keys():
                cat = categories.get(cat_id)
                cat_name = cat.name if cat else "Uncategorized"
                link_name = cat_name.lower().replace(" ", "-")
                f.write(f"- [{cat_name}](#{link_name})\n")
            f.write("\n")
            
            for cat_id, cat_recs in category_records.items():
                cat = categories.get(cat_id)
                cat_name = cat.name if cat else "Uncategorized"
                
                f.write(f"## {cat_name}\n")
                f.write(f"_{len(cat_recs)} records_\n\n")
                
                header_row = "| " + " | ".join(headers) + " |"
                sep_row = "| " + " | ".join(["---"] * len(headers)) + " |"
                
                f.write(header_row + "\n")
                f.write(sep_row + "\n")
                
                for record in cat_recs:
                    values = self._get_record_values(record, fields)
                    values.append(cat_name)
                    values.append(str(record.source_page) if record.source_page else "")
                    
                    safe_values = [str(v).replace("|", "\\|").replace("\n", " ") for v in values]
                    row_str = "| " + " | ".join(safe_values) + " |"
                    f.write(row_str + "\n")
                    
                f.write("\n")
