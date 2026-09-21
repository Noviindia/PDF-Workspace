from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json

class PageType(Enum):
    NATIVE_TEXT = 'NATIVE_TEXT'
    SCANNED = 'SCANNED'
    MIXED = 'MIXED'

@dataclass
class Document:
    id: int
    name: str
    file_path: str
    page_count: int
    doc_type: PageType
    file_size: int
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: tuple) -> Optional['Document']:
        if not row:
            return None
        return cls(
            id=row[0],
            name=row[1],
            file_path=row[2],
            page_count=row[3],
            doc_type=PageType(row[4]) if row[4] else PageType.NATIVE_TEXT,
            file_size=row[5],
            created_at=row[6],
            updated_at=row[7]
        )

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        if isinstance(d.get('doc_type'), PageType):
            d['doc_type'] = d['doc_type'].value
        return d

@dataclass
class Page:
    id: int
    document_id: int
    page_number: int
    raw_text: str
    processed_text: str
    page_type: PageType
    ocr_confidence: Optional[float]
    width: float
    height: float
    has_tables: bool

    @classmethod
    def from_row(cls, row: tuple) -> Optional['Page']:
        if not row:
            return None
        return cls(
            id=row[0],
            document_id=row[1],
            page_number=row[2],
            raw_text=row[3],
            processed_text=row[4],
            page_type=PageType(row[5]) if row[5] else PageType.NATIVE_TEXT,
            ocr_confidence=row[6],
            width=row[7],
            height=row[8],
            has_tables=bool(row[9])
        )

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        if isinstance(d.get('page_type'), PageType):
            d['page_type'] = d['page_type'].value
        return d

@dataclass
class Record:
    id: int
    document_id: int
    page_number: int
    category_id: Optional[int]
    data: dict
    source_text: str
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    created_at: str
    updated_at: str
    is_edited: bool

    @classmethod
    def from_row(cls, row: tuple) -> Optional['Record']:
        if not row:
            return None
        return cls(
            id=row[0],
            document_id=row[1],
            page_number=row[2],
            category_id=row[3],
            data=json.loads(row[4]) if row[4] else {},
            source_text=row[5],
            bbox_x=row[6],
            bbox_y=row[7],
            bbox_w=row[8],
            bbox_h=row[9],
            created_at=row[10],
            updated_at=row[11],
            is_edited=bool(row[12])
        )

    @property
    def source_page(self) -> int:
        return self.page_number

    @source_page.setter
    def source_page(self, value: int):
        self.page_number = value

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d['source_page'] = self.page_number
        return d

@dataclass
class Category:
    id: int
    document_id: int
    name: str
    parent_id: Optional[int]
    record_count: int
    color: Optional[str]
    sort_order: int

    @classmethod
    def from_row(cls, row: tuple) -> Optional['Category']:
        if not row:
            return None
        return cls(
            id=row[0],
            document_id=row[1],
            name=row[2],
            parent_id=row[3],
            record_count=row[4],
            color=row[5],
            sort_order=row[6]
        )

    def to_dict(self) -> dict:
        return self.__dict__.copy()

@dataclass
class BoundingBox:
    id: int
    page_id: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_type: str

    @classmethod
    def from_row(cls, row: tuple) -> Optional['BoundingBox']:
        if not row:
            return None
        return cls(
            id=row[0],
            page_id=row[1],
            text=row[2],
            x0=row[3],
            y0=row[4],
            x1=row[5],
            y1=row[6],
            block_type=row[7]
        )

    def to_dict(self) -> dict:
        return self.__dict__.copy()

@dataclass
class SearchResult:
    text: str
    page_number: int
    category_name: str
    context_snippet: str
    record_id: Optional[int]
    rank: float
    match_field: str = ""

    @classmethod
    def from_row(cls, row: tuple) -> Optional['SearchResult']:
        if not row:
            return None
        return cls(
            text=row[0],
            page_number=row[1],
            category_name=row[2],
            context_snippet=row[3],
            record_id=row[4],
            rank=row[5]
        )

    def to_dict(self) -> dict:
        return self.__dict__.copy()

@dataclass
class UserCorrection:
    id: int
    record_id: int
    field_name: str
    original_value: str
    corrected_value: str
    created_at: str

    @classmethod
    def from_row(cls, row: tuple) -> Optional['UserCorrection']:
        if not row:
            return None
        return cls(
            id=row[0],
            record_id=row[1],
            field_name=row[2],
            original_value=row[3],
            corrected_value=row[4],
            created_at=row[5]
        )

    def to_dict(self) -> dict:
        return self.__dict__.copy()

@dataclass
class ProjectMeta:
    id: int
    key: str
    value: str

    @classmethod
    def from_row(cls, row: tuple) -> Optional['ProjectMeta']:
        if not row:
            return None
        return cls(
            id=row[0],
            key=row[1],
            value=row[2]
        )

    def to_dict(self) -> dict:
        return self.__dict__.copy()

@dataclass
class TableData:
    id: int
    page_id: int
    document_id: int
    page_number: int
    headers: List[str]
    rows: List[List[str]]
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float

    @classmethod
    def from_row(cls, row: tuple) -> Optional['TableData']:
        if not row:
            return None
        return cls(
            id=row[0],
            page_id=row[1],
            document_id=row[2],
            page_number=row[3],
            headers=json.loads(row[4]) if row[4] else [],
            rows=json.loads(row[5]) if row[5] else [],
            bbox_x=row[6],
            bbox_y=row[7],
            bbox_w=row[8],
            bbox_h=row[9]
        )

    def to_dict(self) -> dict:
        return self.__dict__.copy()

@dataclass
class ExportConfig:
    format: str
    scope: str = 'all'
    category_id: Optional[int] = None
    record_ids: Optional[List[int]] = None
    search_query: Optional[str] = None
    output_path: str = ''

    def to_dict(self) -> dict:
        return self.__dict__.copy()
