# Atlas dos Acórdãos V14 Realista

Versão revisada do sistema com foco em:
- auditoria de citações geradas por IA
- validação em base própria
- correção automática de acórdão, jurisprudência e súmula
- match semântico por tese
- reescrita jurídica contextual do parágrafo

## Como usar
1. Coloque seus arquivos `.db` em `data/base/`
2. Instale as dependências:
   `pip install -r requirements.txt`
3. Execute:
   `streamlit run app.py`


## Base inteligente

O sistema agora prioriza automaticamente um arquivo `data/base/base_inteligente.db` quando ele existir.

Passos:

1. Gere a base inteligente com o pacote `base_inteligente_atlas`.
2. Copie `base_inteligente.db` para `data/base/`.
3. Rode o app normalmente.

Enquanto a base inteligente não existir, o sistema continua funcionando com as bases `.db` brutas já existentes.
