# Atlas de Acórdãos MS — Versão final cliente

Principais entregas desta versão:
- classificação mais robusta entre recurso, contrarrazão e impugnação
- auditoria da citação já existente na peça
- correção sugerida quando o acórdão citado não é compatível ou não é localizado
- até 2 teses curtas e aplicadas para reforço argumentativo
- download da peça corrigida em DOCX e PDF
- interface mais comercial, limpa e responsiva

## Estrutura esperada

Coloque seus bancos SQLite em:

`data/base/`

## Executar localmente

```bash
streamlit run app.py
```

## Deploy

Suba o conteúdo desta pasta para o GitHub e publique apontando para `app.py`.
