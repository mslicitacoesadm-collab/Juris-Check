# Validador de Acórdãos e Jurisprudência

Sistema em **Streamlit** para:

- validar citações de acórdãos em recursos, contrarrazões e impugnações;
- localizar divergências numéricas;
- sugerir acórdãos aderentes com base semântica;
- gerar relatório exportável em Markdown e CSV.

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
├── assets/
└── modules/
    ├── base_loader.py
    ├── piece_reader.py
    ├── citation_extractor.py
    ├── matcher.py
    └── report_builder.py
```

## Como usar

1. Coloque seus JSONs anuais em `data/acordaos/`
2. Instale as dependências:
   `pip install -r requirements.txt`
3. Rode:
   `streamlit run app.py`

## Schema esperado

```json
{
  "id": "ACORDAO-COMPLETO-2230911",
  "tipo": "ACÓRDÃO",
  "titulo": "ACÓRDÃO 3215/2016 ATA 40/2016 - PLENÁRIO",
  "numero_acordao": "3215/2016",
  "numero_acordao_num": "3215",
  "ano_acordao": "2016",
  "colegiado": "PLENÁRIO",
  "data_sessao": "07/12/2016",
  "relator": "MINISTRO XXXXX",
  "processo": "XXXXX/2016-0",
  "assunto": "Representação sobre irregularidades em licitação",
  "sumario": "Trecho resumido da tese jurídica",
  "ementa_match": "licitação, diligência, inexequibilidade, saneamento",
  "decisao": "texto resumido da decisão",
  "url_oficial": "",
  "status": "ativo",
  "tags": ["licitação", "inexequibilidade", "diligência", "saneamento"]
}
```

## Observações

- A V1 é 100% GitHub + Streamlit, sem API externa.
- O sistema não inventa números; só cruza com a base que você colocar.
- Suporta PDF, DOCX e TXT.
- Ainda não faz OCR.
