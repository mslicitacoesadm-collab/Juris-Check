from __future__ import annotations

import sqlite3
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


def summarize_bases(base_dir: Path) -> Dict[str, Any]:
    dbs = find_db_files(base_dir)
    total_registros = 0
    anos = []
    detalhes = []
    for db in dbs:
        try:
            conn = open_db(db)
            row = conn.execute('SELECT ano, total_registros FROM metadata LIMIT 1').fetchone()
            if row:
                total_registros += int(row['total_registros'] or 0)
                anos.append(str(row['ano']))
                detalhes.append({'arquivo': db.name, 'ano': str(row['ano']), 'total_registros': int(row['total_registros'] or 0)})
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
        try:
            if ano:
                row = conn.execute(
                    'SELECT * FROM records WHERE numero_acordao_num = ? AND ano_acordao = ? LIMIT 1',
                    (numero, ano),
                ).fetchone()
            else:
                row = conn.execute('SELECT * FROM records WHERE numero_acordao_num = ? LIMIT 1', (numero,)).fetchone()
            if row:
                return dict(row)
        finally:
            conn.close()
    return None
