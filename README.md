# Atlas de Acórdãos MS · V7 Premium

Versão refinada do sistema com suporte a três camadas de precedentes:

- acórdãos
- jurisprudência selecionada
- súmulas

## O que mudou

- validação automática de citações de **acórdão** e **súmula**;
- busca por **jurisprudência** quando ela encaixar melhor na tese;
- sugestão mista por tese, com possibilidade de recomendar **acórdão + jurisprudência + súmula**;
- correção textual automática da peça com substituição de citações fracas ou divergentes;
- métricas separadas da base por tipo de precedente.

## Estrutura esperada da base

Coloque os arquivos `.db` em:

`data/base/`

O sistema detecta automaticamente tabelas compatíveis com:

- `acordaos`
- `jurisprudencia`
- `sumula`

## Execução

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Observação

Este pacote foi entregue **sem a base**, como solicitado.
