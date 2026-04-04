# Validador de Acórdãos e Jurisprudência

Sistema em **Streamlit** para:

- validar citações de acórdãos em recursos, contrarrazões e impugnações;
- localizar divergências numéricas;
- sugerir acórdãos aderentes com base semântica;
- gerar relatório exportável em Markdown e CSV.

## Ajustes desta revisão

- correção da estrutura de pastas vazias (`data/acordaos`, `assets`, `exports`);
- cache de carregamento da base e do índice TF-IDF;
- redução do consumo de memória na análise;
- tratamento mais robusto de JSON com BOM (`utf-8-sig`);
- deduplicação de registros da base;
- normalização de status (`ativo`, `sigiloso`, `desconhecido`).

## Estrutura

```bash
jurisprudencia_match_system/
├── app.py
├── requirements.txt
├── README.md
├── run_local.bat
├── data/
│   └── acordaos/
│       └── .gitkeep
├── exports/
│   └── .gitkeep
├── assets/
│   └── .gitkeep
└── modules/
    ├── __init__.py
    ├── base_loader.py
    ├── piece_reader.py
    ├── citation_extractor.py
    ├── matcher.py
    └── report_builder.py
```

## Como usar

1. Coloque seus JSONs anuais em `data/acordaos/`
2. Instale as dependências: `pip install -r requirements.txt`
3. Rode: `streamlit run app.py`

## Observações

- A V1 é 100% GitHub + Streamlit, sem API externa.
- O sistema não inventa números; só cruza com a base que você colocar.
- Suporta PDF, DOCX e TXT.
- Ainda não faz OCR.
