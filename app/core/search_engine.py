import sqlite3
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import re

from app.database.models import SearchResult


class SearchEngine:
    """Offline full-text search engine powered by SQLite FTS5."""

    def __init__(self, db_repository):
        self.db = db_repository

    def build_index(self, document_id: int):
        """Builds FTS index for a document."""
        return self.db.rebuild_search_index(document_id)

    def search(self, query: str, document_id: Optional[int] = None, category_id: Optional[int] = None, limit: int = 500, doc_id: Optional[int] = None, scope: str = 'all') -> List[SearchResult]:
        """Perform full-text search across pages and records."""
        if document_id is None and doc_id is not None:
            document_id = doc_id
        clean_query = query.strip()
        if not clean_query:
            return []

        if category_id is not None:
            return self.db.search_in_category(clean_query, category_id, limit, scope=scope)
        return self.db.search(clean_query, document_id, limit, scope=scope)

    def search_dict(self, query: str, document_id: Optional[int] = None, category_id: Optional[int] = None, limit: int = 500, doc_id: Optional[int] = None, scope: str = 'all') -> List[Dict[str, Any]]:
        """Perform full-text search returning plain dictionaries."""
        if document_id is None and doc_id is not None:
            document_id = doc_id
        results = self.search(query, document_id, category_id, limit, scope=scope)
        return [r.to_dict() if hasattr(r, 'to_dict') else dict(r) for r in results]

    def _prepare_query(self, raw_query: str) -> str:
        """Sanitize and prepare FTS5 query."""
        query = re.sub(r'[^\w\s*"-]', ' ', raw_query).strip()
        if not query:
            return ""
        if '"' not in query:
            terms = query.split()
            if terms:
                terms[-1] = f"{terms[-1]}*"
                query = " ".join(terms)
        return query

    def get_suggestions(self, partial_query: str, document_id: int, limit: int = 5) -> List[str]:
        """Autocomplete suggestions."""
        results = self.search(partial_query, document_id, limit=limit)
        suggestions = []
        for r in results:
            snippet = r.context_snippet if hasattr(r, 'context_snippet') else r.get('context_snippet', '')
            if snippet and snippet not in suggestions:
                suggestions.append(snippet)
        return suggestions

    def clear_index(self, document_id: int):
        """Remove all index entries for a document."""
        self.db.clear_fts_index(document_id)

