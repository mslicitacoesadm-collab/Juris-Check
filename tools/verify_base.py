from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def verify(db_path: Path) -> str:
    if not db_path.exists():
        return 'arquivo_nao_encontrado'
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute('PRAGMA integrity_check').fetchone()
        return str(row[0]) if row else 'erro'
    except Exception as exc:
        return f'erro: {exc}'
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Valida a integridade do SQLite.')
    parser.add_argument('db_path', help='Caminho para o banco .db')
    args = parser.parse_args()
    print(verify(Path(args.db_path)))


if __name__ == '__main__':
    main()
