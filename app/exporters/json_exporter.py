import json
from datetime import datetime
from typing import List, Dict
from app.exporters.base_exporter import BaseExporter
from app.database.models import Record, Category

class JSONExporter(BaseExporter):
    """JSON export."""
    
    def export_records(self, records: List[Record], output_path: str, document_name: str, categories: Dict[int, Category]):
        fields = self._get_field_names(records)
        
        category_names = [c.name for c in categories.values()]
        
        data = {
            "document": {
                "name": document_name,
                "exported_at": datetime.now().isoformat(),
                "total_records": len(records),
                "categories": category_names
            },
            "fields": fields + ['category', 'source_page'],
            "records": []
        }
        
        for record in records:
            rec_dict = {}
            if isinstance(record.data, dict):
                rec_dict.update(record.data)
                
            cat = categories.get(record.category_id)
            rec_dict['category'] = cat.name if cat else ""
            rec_dict['source_page'] = record.source_page
            
            data["records"].append(rec_dict)
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
