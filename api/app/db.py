import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/app/data/db.sqlite3")

def _dict_factory(cursor, row):
    """Converte rows do sqlite em dicts (coluna -> valor)."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@contextmanager
def get_conn(readonly=True):
    """
    Abre conexão com SQLite.
    - Se readonly=True, usa modo somente leitura (para SELECTs).
    - Se readonly=False, abre normal (para inserts/updates).
    """
    uri = f"file:{DB_PATH}?mode=ro" if readonly else f"file:{DB_PATH}?mode=rwc"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = _dict_factory
    try:
        # Garante integridade referencial
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        conn.close()