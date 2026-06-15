"""Database schema: 7 tables for CTF binary analysis data."""

import sqlite3
import os
from ..config import DB_PATH


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self):
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    sha256 TEXT,
                    arch TEXT,
                    bits INTEGER,
                    endian TEXT,
                    difficulty TEXT DEFAULT 'unknown',
                    tags TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id INTEGER REFERENCES samples(id),
                    task_type TEXT DEFAULT 'full_analysis',
                    status TEXT DEFAULT 'pending',
                    flag TEXT,
                    elapsed_seconds REAL,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER REFERENCES tasks(id),
                    round_number INTEGER,
                    tool_name TEXT NOT NULL,
                    arguments TEXT DEFAULT '{}',
                    output TEXT,
                    success INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS intermediate_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER REFERENCES tasks(id),
                    result_type TEXT NOT NULL,
                    data TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS agent_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER REFERENCES tasks(id),
                    round_number INTEGER,
                    memory_type TEXT NOT NULL,
                    content TEXT,
                    context TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER REFERENCES tasks(id),
                    flag TEXT NOT NULL,
                    explanation TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_set TEXT,
                    total_samples INTEGER DEFAULT 0,
                    total_tasks INTEGER DEFAULT 0,
                    successful_tasks INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    by_difficulty TEXT DEFAULT '{}',
                    by_arch TEXT DEFAULT '{}',
                    details TEXT DEFAULT '{}',
                    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
