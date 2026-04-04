# Validador de Autoridade Jurídica

Sistema em Streamlit para validar citações de acórdãos e sugerir reforço jurisprudencial com base em arquivos JSON/JSONL locais.

## Estrutura

- `app.py` — aplicação principal
- `modules/` — módulos do sistema
- `data/acordaos/` — pasta onde você colocará a base
- `exports/` — pasta reservada para saídas futuras

## Como usar

1. Coloque seus arquivos `.json` ou `.jsonl` em `data/acordaos/`
2. Suba a pasta no GitHub
3. Aponte o Streamlit para `app.py`

## Observações

- Esta versão não inclui os acórdãos no pacote.
- O app abre normalmente mesmo sem base.
- A análise só é liberada quando houver registros em `data/acordaos/`.
- Esta versão não depende de `scikit-learn`, o que reduz risco de falha de instalação no Streamlit Cloud.
