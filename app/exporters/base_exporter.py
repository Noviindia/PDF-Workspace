import os
import re
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
from app.database.models import Record, Category, ExportConfig

class BaseExporter(ABC):
    """Abstract base class for all exporters."""
    
    def __init__(self, repository):
        self.repository = repository
        
    def export(self, config: ExportConfig) -> str:
        """Main export method, returns output file path."""
        records, title = self._get_records_for_config(config)
        categories = {c.id: c for c in self.repository.get_categories()}
        
        output_dir = os.path.dirname(config.output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
        self.export_records(records, config.output_path, title, categories)
        return config.output_path

    @abstractmethod
    def export_records(self, records: List[Record], output_path: str, document_name: str, categories: Dict[int, Category]):
        """Abstract method to implement export logic for specific formats."""
        pass

    def _get_records_for_config(self, config: ExportConfig) -> Tuple[List[Record], str]:
        """Gets records and a title based on config."""
        if config.scope == 'all':
            return self.repository.get_all_records(), "All Records"
        elif config.scope == 'category':
            if not config.category_id:
                raise ValueError("category_id is required when scope is 'category'")
            category = self.repository.get_category(config.category_id)
            title = category.name if category else "Category Export"
            return self.repository.get_records_by_category(config.category_id), title
        elif config.scope == 'selected':
            if not config.record_ids:
                raise ValueError("record_ids is required when scope is 'selected'")
            return self.repository.get_records_by_ids(config.record_ids), "Selected Records"
        elif config.scope == 'search':
            if not config.search_query:
                raise ValueError("search_query is required when scope is 'search'")
            return self.repository.search_records(config.search_query), f"Search Results: {config.search_query}"
        else:
            raise ValueError(f"Unknown export scope: {config.scope}")

    CANONICAL_ORDER = [
        'serial_no', 'voter_id', 'epic_no', 'name', 'relation_name',
        'relation_type', 'father_name', 'husband_name', 'house_no',
        'village', 'address', 'age', 'gender', 'roll_no', 'class', 'section'
    ]

    def _get_field_names(self, records: List[Record]) -> List[str]:
        """Collects all relevant unique field names across records, ordered canonically."""
        key_counts: Dict[str, int] = {}
        for record in records:
            if isinstance(record.data, dict):
                for key in record.data.keys():
                    key_counts[key] = key_counts.get(key, 0) + 1

        if not key_counts:
            return []

        def is_valid_key(k: str) -> bool:
            k_str = str(k).strip()
            if not k_str:
                return False
            # Reject pure numbers or punctuation (like '6', '679', '_', '4:', '/')
            if re.match(r'^[\d\s\W_]+$', k_str):
                return False
            # Single latin char noise (e.g. 'w', 's')
            if len(k_str) == 1 and not re.search(r'[\u0900-\u097F]', k_str):
                return False
            return True

        valid_keys = {k for k in key_counts if is_valid_key(k)}

        # If canonical fields exist, filter out ultra-sparse noise (< 10% presence if > 10 records)
        total_recs = len(records)
        if total_recs >= 10:
            has_canonical = any(k in self.CANONICAL_ORDER for k in valid_keys)
            if has_canonical:
                threshold = max(2, int(total_recs * 0.10))
                valid_keys = {k for k in valid_keys if key_counts[k] >= threshold}

        # Order canonical keys first
        ordered_fields = []
        for ck in self.CANONICAL_ORDER:
            if ck in valid_keys:
                ordered_fields.append(ck)

        # Append remaining valid keys
        for record in records:
            if isinstance(record.data, dict):
                for key in record.data.keys():
                    if key in valid_keys and key not in ordered_fields:
                        ordered_fields.append(key)

        return ordered_fields

    def _get_display_field_name(self, key: str) -> str:
        """Map technical field name to user-friendly column header."""
        display_map = {
            'serial_no': 'Serial No (क्र. सं.)',
            'voter_id': 'Voter ID / EPIC',
            'epic_no': 'EPIC No.',
            'name': 'Name (नाम)',
            'relation_name': 'Father / Relative Name (पिता/सम्बन्धी का नाम)',
            'relation_type': 'Relation (संबंध)',
            'father_name': "Father's Name (पिता का नाम)",
            'husband_name': "Husband's Name (पति का नाम)",
            'house_no': 'House No / Village (मकान/ग्राम)',
            'village': 'Village (ग्राम)',
            'address': 'Address (पता)',
            'age': 'Age (उम्र)',
            'gender': 'Gender (लिंग)',
            'roll_no': 'Roll No',
            'class': 'Class',
            'section': 'Section',
        }
        if key in display_map:
            return display_map[key]
        return key.replace('_', ' ').strip().title()

    def _get_record_values(self, record: Record, field_names: List[str]) -> List[str]:
        """Extract values for given fields from a record's data dict."""
        values = []
        data = record.data if isinstance(record.data, dict) else {}
        for field in field_names:
            val = data.get(field, "")
            values.append(str(val))
        return values

    def _sanitize_filename(self, name: str) -> str:
        """Make filename safe."""
        name = re.sub(r'[^\w\s-]', '', name)
        return name.strip().replace(' ', '_')
