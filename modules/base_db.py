from __future__ import annotations
from pathlib import Path
import sqlite3


def find_db_files(base_dir: Path):
    if not base_dir.exists():
        return []
    return sorted([p for p in base_dir.glob('*.db') if p.is_file()])


def _count_table(path: Path, table: str) -> int:
    try:
        con = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=2)
        cur = con.cursor()
        return int(cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
    except Exception:
        return 0
    finally:
        try: con.close()
        except Exception: pass


def summarize_bases(base_dir: Path):
    files = find_db_files(base_dir)
    total = 0
    bad = 0
    for p in files:
        n = _count_table(p, 'acordaos')
        if n == 0:
            bad += 1
        total += n
    return {
        'total_bases': len(files),
        'total_files': len(files),
        'arquivos_invalidos': bad,
        'total_size_mb': round(sum(p.stat().st_size for p in files) / (1024*1024), 1),
        'acordao': total,
        'jurisprudencia': 0,
        'sumula': 0,
        'inteligente': total,
        'base_inteligente_detectada': any(p.name == 'base_inteligente.db' for p in files),
        'arquivo_base_inteligente': 'base_inteligente.db' if any(p.name == 'base_inteligente.db' for p in files) else '',
    }
