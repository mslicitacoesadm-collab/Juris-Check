# Atlas de Acórdãos V3

Versão com leitura por tese jurídica para recurso, contrarrazão e impugnação.

## O que mudou na V3

- leitura da peça por **tese jurídica**
- menos ruído visual
- sugestões curtas em formato aproveitável
- compatibilidade com bases SQLite heterogêneas
- estrutura pronta para GitHub + Streamlit

## Como aplicar

1. extraia este pacote
2. mantenha seus bancos `.db` em `data/base/`
3. suba a pasta para o GitHub
4. publique no Streamlit apontando para `app.py`

## Estrutura esperada da base

Coloque os bancos em:

```text
data/base/acordaos_2016.db
data/base/acordaos_2017.db
...
```

## Observações

- o sistema trabalha com **acórdãos do TCU**
- a sugestão é de apoio e deve ser validada antes do protocolo
- quando a aderência for fraca, o sistema prefere não sugerir
