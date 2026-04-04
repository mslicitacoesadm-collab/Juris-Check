from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

DB_GLOB = 'acordaos_*.db'


def find_db_files(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    return sorted(base_dir.glob(DB_GLOB))


def open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=128)
def detect_schema(db_path_str: str) -> str:
    db_path = Path(db_path_str)
    conn = open_db(db_path)
    try:
        tables = {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'records' in tables:
            return 'records'
        if 'acordaos' in tables:
            return 'acordaos'
        return 'unknown'
    finally:
        conn.close()


def summarize_bases(base_dir: Path) -> Dict[str, Any]:
    dbs = find_db_files(base_dir)
    total_registros = 0
    anos = []
    detalhes = []
    for db in dbs:
        schema = detect_schema(str(db))
        try:
            conn = open_db(db)
            if schema == 'records':
                row = conn.execute('SELECT ano, total_registros FROM metadata LIMIT 1').fetchone()
                if row:
                    ano = str(row['ano'])
                    total = int(row['total_registros'] or 0)
                else:
                    ano = db.stem[-4:]
                    total = conn.execute('SELECT COUNT(*) AS c FROM records').fetchone()['c']
            elif schema == 'acordaos':
                row = conn.execute('SELECT COUNT(*) AS c, MIN(ano_acordao) AS ano FROM acordaos').fetchone()
                ano = str(row['ano'] or db.stem[-4:])
                total = int(row['c'] or 0)
            else:
                ano = '?'
                total = 0
            total_registros += total
            if ano and ano != '?':
                anos.append(ano)
            detalhes.append({'arquivo': db.name, 'ano': ano, 'total_registros': total})
            conn.close()
        except Exception:
            detalhes.append({'arquivo': db.name, 'ano': '?', 'total_registros': 0})
    anos = sorted({a for a in anos if a})
    return {
        'total_bases': len(dbs),
        'total_registros': total_registros,
        'anos': anos,
        'detalhes': detalhes,
    }


def exact_lookup(db_files: Iterable[Path], numero: str, ano: str | None = None) -> Dict[str, Any] | None:
    if not numero:
        return None
    for db in db_files:
        conn = open_db(db)
        schema = detect_schema(str(db))
        try:
            table = 'records' if schema == 'records' else 'acordaos' if schema == 'acordaos' else None
            if not table:
                continue
            if ano:
                row = conn.execute(
                    f'SELECT * FROM {table} WHERE numero_acordao_num = ? AND ano_acordao = ? LIMIT 1',
                    (numero, ano),
                ).fetchone()
            else:
                row = conn.execute(f'SELECT * FROM {table} WHERE numero_acordao_num = ? LIMIT 1', (numero,)).fetchone()
            if row:
                return dict(row)
        finally:
            conn.close()
    return None
