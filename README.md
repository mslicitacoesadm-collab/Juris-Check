# Atlas dos Acórdãos V13 Profissional

Sistema em Streamlit para auditoria de citações jurídicas em peças licitatórias.

## Como usar
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Coloque seus arquivos `.db` em `data/base/`.
3. Execute:
   ```bash
   streamlit run app.py
   ```

## O foco da ferramenta
- validar citação de acórdão, súmula e jurisprudência digitada na peça
- localizar divergências entre o texto e a base
- sugerir precedentes melhores para a tese
- reescrever o trecho com linguagem mais natural
- exportar peça revisada e relatório de auditoria
