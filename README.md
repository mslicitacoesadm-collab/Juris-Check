# Atlas de Precedentes MS — V8 Premium

Principais entregas desta versão:
- auditoria de citações de acórdãos já usadas na peça
- reforço por tese com combinação entre acórdão, jurisprudência e súmula
- nova aba de **busca manual de precedentes**
- pesquisa por **tese** ou por **referência direta**
- exibição do motivo da sugestão e parágrafo pronto para uso
- download da peça corrigida em DOCX e PDF

## Estrutura esperada

Coloque seus bancos SQLite em:

`data/base/`

A pasta aceita bases de:
- acórdãos
- jurisprudência
- súmulas

## Executar localmente

```bash
streamlit run app.py
```

## Deploy

Suba o conteúdo desta pasta para o GitHub e publique apontando para `app.py`.
