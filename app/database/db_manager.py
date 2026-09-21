import sqlite3
import os
import threading
from typing import Any, List, Optional, Tuple

class DatabaseManager:
    """Manages SQLite database connections and schema for the PDF Workspace application."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            # Ensure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON;')
            conn.execute('PRAGMA journal_mode = WAL;')
            self._local.connection = conn
        return self._local.connection

    def close(self):
        """Close the thread-local database connection."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            del self._local.connection

    def initialize(self):
        """Creates all necessary tables if they don't exist."""
        sql_script = """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            page_count INTEGER DEFAULT 0,
            doc_type TEXT DEFAULT 'NATIVE_TEXT',
            file_size INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            raw_text TEXT DEFAULT '',
            processed_text TEXT DEFAULT '',
            page_type TEXT DEFAULT 'NATIVE_TEXT',
            ocr_confidence REAL,
            width REAL DEFAULT 0,
            height REAL DEFAULT 0,
            has_tables INTEGER DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            category_id INTEGER,
            data TEXT DEFAULT '{}',
            source_text TEXT DEFAULT '',
            bbox_x REAL DEFAULT 0, bbox_y REAL DEFAULT 0,
            bbox_w REAL DEFAULT 0, bbox_h REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_edited INTEGER DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            record_count INTEGER DEFAULT 0,
            color TEXT,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS bounding_boxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id INTEGER NOT NULL,
            text TEXT DEFAULT '',
            x0 REAL DEFAULT 0, y0 REAL DEFAULT 0,
            x1 REAL DEFAULT 0, y1 REAL DEFAULT 0,
            block_type TEXT DEFAULT 'text',
            FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS user_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            original_value TEXT DEFAULT '',
            corrected_value TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS table_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id INTEGER,
            document_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            headers TEXT DEFAULT '[]',
            rows TEXT DEFAULT '[]',
            bbox_x REAL DEFAULT 0, bbox_y REAL DEFAULT 0,
            bbox_w REAL DEFAULT 0, bbox_h REAL DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS project_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT DEFAULT ''
        );

        -- FTS5 for full-text search
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
            text,
            page_number UNINDEXED,
            document_id UNINDEXED,
            record_id UNINDEXED,
            category_name UNINDEXED,
            tokenize='porter unicode61'
        );
        """
        conn = self.get_connection()
        try:
            conn.executescript(sql_script)
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error initializing database: {e}")
            conn.rollback()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Executes a SQL statement and returns the last inserted row id."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.lastrowid or 0
        except sqlite3.Error as e:
            print(f"Database error on execute: {e} - Query: {sql}")
            conn.rollback()
            return 0

    def executemany(self, sql: str, params_list: List[tuple]) -> bool:
        """Executes a SQL statement for multiple parameter sets."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error on executemany: {e}")
            conn.rollback()
            return False

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[tuple]:
        """Executes a SQL query and returns the first row."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Database error on fetchone: {e}")
            return None

    def fetchall(self, sql: str, params: tuple = ()) -> List[tuple]:
        """Executes a SQL query and returns all rows."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error on fetchall: {e}")
            return []
