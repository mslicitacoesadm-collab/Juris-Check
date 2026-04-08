
from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
PACKAGE_DIR = PROJECT_DIR / 'base_inteligente_atlas'
BASE_DIR = PROJECT_DIR / 'data' / 'base'


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    src = PACKAGE_DIR / 'base_inteligente.db'
    if not src.exists():
        print('Nenhum arquivo base_inteligente.db foi encontrado em base_inteligente_atlas/.')
        print('Coloque a base gerada nessa pasta e rode este script novamente.')
        return
    dest = BASE_DIR / 'base_inteligente.db'
    shutil.copy2(src, dest)
    print(f'Base inteligente instalada em: {dest}')


if __name__ == '__main__':
    main()
