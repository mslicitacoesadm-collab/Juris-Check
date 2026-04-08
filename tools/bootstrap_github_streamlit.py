from __future__ import annotations

from pathlib import Path
import zipfile

from tools.rebuild_base_from_parts import rebuild
from tools.verify_base import verify

PARTS_DIR_NAME = 'base_inteligente_atlas'
OUTPUT_DB_RELATIVE = Path('data/base/base_inteligente.db')
PART_PREFIX = 'base_inteligente_completa_funcional.db.part_'


def _extract_zip_parts(parts_dir: Path) -> int:
    extracted = 0
    for zip_path in sorted(parts_dir.glob('*.zip')):
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                name = Path(member).name
                if name.startswith(PART_PREFIX) and not (parts_dir / name).exists():
                    target = parts_dir / name
                    target.write_bytes(zf.read(member))
                    extracted += 1
    return extracted


def ensure_base_ready(base_dir: Path | None = None) -> dict:
    root = Path(base_dir or Path.cwd())
    parts_dir = root / PARTS_DIR_NAME
    output_db = root / OUTPUT_DB_RELATIVE
    output_db.parent.mkdir(parents=True, exist_ok=True)

    if output_db.exists():
        integrity = verify(output_db)
        return {
            'ready': integrity == 'ok',
            'message': f'Base já encontrada em {output_db}. Integridade: {integrity}.',
            'db_path': str(output_db),
            'integrity': integrity,
        }

    if not parts_dir.exists():
        return {
            'ready': False,
            'message': f'Pasta de partes não encontrada: {parts_dir}. Coloque as partes ou ZIPs em {PARTS_DIR_NAME}/.',
            'db_path': str(output_db),
        }

    extracted = _extract_zip_parts(parts_dir)
    parts = sorted(parts_dir.glob(f'{PART_PREFIX}*'))
    if not parts:
        return {
            'ready': False,
            'message': f'Nenhuma parte encontrada em {parts_dir}. Extraia os arquivos .part_* ou envie os ZIPs das partes para essa pasta.',
            'db_path': str(output_db),
        }

    rebuilt = rebuild(parts_dir, output_db, PART_PREFIX)
    integrity = verify(rebuilt)
    extra = f' {extracted} arquivo(s) ZIP extraído(s).' if extracted else ''
    return {
        'ready': integrity == 'ok',
        'message': f'Base montada automaticamente em {rebuilt}. Integridade: {integrity}.{extra}',
        'db_path': str(rebuilt),
        'integrity': integrity,
        'parts_found': len(parts),
        'zip_extracted': extracted,
    }


def main() -> None:
    result = ensure_base_ready()
    print(result.get('message', 'Sem retorno do bootstrap.'))
    if not result.get('ready', False):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
