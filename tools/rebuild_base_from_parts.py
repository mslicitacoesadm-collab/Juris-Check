from __future__ import annotations

import argparse
from pathlib import Path

from tools.verify_base import verify


def _ordered_parts(parts_dir: Path, prefix: str):
    parts = sorted(parts_dir.glob(f'{prefix}*'))
    if not parts:
        raise FileNotFoundError(f'Nenhuma parte encontrada em {parts_dir} com prefixo {prefix}')
    return parts


def rebuild(parts_dir: Path, output_file: Path, prefix: str = 'base_inteligente_completa_funcional.db.part_') -> Path:
    parts = _ordered_parts(parts_dir, prefix)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output_file.with_suffix(output_file.suffix + '.tmp')
    if tmp_output.exists():
        tmp_output.unlink()
    with tmp_output.open('wb') as out:
        for part in parts:
            out.write(part.read_bytes())
    integrity = verify(tmp_output)
    if integrity != 'ok':
        tmp_output.unlink(missing_ok=True)
        raise RuntimeError(f'Falha na integridade do banco reconstruído: {integrity}')
    tmp_output.replace(output_file)
    return output_file


def main() -> None:
    parser = argparse.ArgumentParser(description='Reconstrói a base inteligente a partir das partes fragmentadas e valida a integridade antes da troca final.')
    parser.add_argument('--parts-dir', default='base_inteligente_atlas', help='Pasta com as partes da base inteligente.')
    parser.add_argument('--output', default='data/base/base_inteligente.db', help='Arquivo de saída.')
    parser.add_argument('--prefix', default='base_inteligente_completa_funcional.db.part_', help='Prefixo dos arquivos de partes.')
    args = parser.parse_args()
    output = rebuild(Path(args.parts_dir), Path(args.output), args.prefix)
    print(f'Base reconstruída com sucesso em: {output}')
    print('Integridade: ok')


if __name__ == '__main__':
    main()
