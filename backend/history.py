"""Local plaintext task history, with a fresh connection for each operation."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

DATABASE_PATH = Path(__file__).resolve().parent / 'data' / 'history.sqlite3'
ERROR_MESSAGE = 'Historikken kunne ikke indlæses. Prøv igen senere.'
SAVE_WARNING = 'Agentsvaret er klar, men opgaven kunne ikke gemmes i historikken.'


@contextmanager
def connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(DATABASE_PATH)
    database.row_factory = sqlite3.Row
    try:
        with database:
            database.execute('''CREATE TABLE IF NOT EXISTS research_history (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                agent TEXT NOT NULL, version TEXT NOT NULL,
                task TEXT NOT NULL, response TEXT NOT NULL
            )''')
            yield database
    finally:
        database.close()


def save(task: str, response: str, agent: str, version: str):
    identifier = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    with connection() as database:
        database.execute(
            'INSERT INTO research_history VALUES (?, ?, ?, ?, ?, ?)',
            (identifier, timestamp, agent, version, task, response),
        )
    return identifier


def recent(agent: str = 'Research Agent'):
    with connection() as database:
        rows = database.execute('''SELECT id, created_at, agent, version,
            substr(task, 1, 160) AS task_excerpt
            FROM research_history WHERE agent = ? ORDER BY created_at DESC, rowid DESC LIMIT 50''', (agent,)).fetchall()
    return [dict(row) for row in rows]


def detail(identifier: str, agent: str = 'Research Agent'):
    with connection() as database:
        row = database.execute(
            'SELECT * FROM research_history WHERE id = ? AND agent = ?', (identifier, agent),
        ).fetchone()
    return dict(row) if row else None
