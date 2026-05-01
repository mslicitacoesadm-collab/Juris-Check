from __future__ import annotations
from pathlib import Path
import sqlite3


def find_db_files(base_dir: Path):
    if not base_dir.exists():
        return []
    return sorted(base_dir.glob('*.db'))


def _count_tables(db_path: Path):
    counts = {'acordao':0,'jurisprudencia':0,'sumula':0,'inteligente':0}
    try:
        con=sqlite3.connect(str(db_path), timeout=3)
        cur=con.cursor()
        tables=[r[0] for r in cur.execute("select name from sqlite_master where type='table'").fetchall()]
        for t in tables:
            low=t.lower()
            try:
                n=cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            except Exception:
                n=0
            if 'intelig' in low or 'preced' in low:
                counts['inteligente'] += n
            elif 'sum' in low:
                counts['sumula'] += n
            elif 'juris' in low:
                counts['jurisprudencia'] += n
            else:
                counts['acordao'] += n
        con.close()
    except Exception:
        pass
    return counts


def summarize_bases(base_dir: Path):
    files=find_db_files(base_dir)
    total={'acordao':0,'jurisprudencia':0,'sumula':0,'inteligente':0}
    for f in files[:25]:
        c=_count_tables(f)
        for k,v in c.items(): total[k]+=v
    return {
        'total_bases': len(files),
        'acordao': total['acordao'],
        'jurisprudencia': total['jurisprudencia'],
        'sumula': total['sumula'],
        'inteligente': total['inteligente'],
        'base_inteligente_detectada': total['inteligente']>0,
        'arquivo_base_inteligente': files[0].name if files else ''
    }
