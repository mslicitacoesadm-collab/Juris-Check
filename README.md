# Atlas dos Acórdãos — sistema evoluído sem a base inteligente

Esta entrega foi preparada para **GitHub + Streamlit**, sem embarcar a base pesada no repositório.

## O que o sistema faz
- lê **PDF, DOCX e TXT**
- identifica o tipo da peça e a tese dominante
- audita citações de acórdãos, jurisprudências e súmulas
- aponta compatibilidade, risco técnico e correções sugeridas
- exporta resultado em **DOCX limpo, DOCX marcado, PDF e CSV**

## O que mudou nesta versão
1. tela inicial mais comercial e mais clara
2. mensagens de erro mais humanas
3. limite recomendado de upload em 20 MB
4. três modos visíveis de análise
5. resultado dividido em blocos claros
6. score comunicado com rótulos comerciais
7. painel administrativo separado do usuário
8. OCR opcional, não obrigatório
9. reconstrução automática da base com validação
10. README técnico e operacional para deploy

## Estrutura esperada
- `data/base/base_inteligente.db` para a base inteligente pronta
- ou as bases tradicionais `.db` em `data/base/`
- opcionalmente, partes da base em `base_inteligente_atlas/`

## Como subir no Streamlit
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Como reconstruir a base por partes
```bash
python tools/bootstrap_github_streamlit.py
```

## Como validar a base
```bash
python tools/verify_base.py data/base/base_inteligente.db
```

## O que subir no GitHub
- `app.py`
- `modules/`
- `tools/`
- `tests/`
- `.gitignore`
- `requirements.txt`
- `README.md`
- pasta `data/base/` vazia com `.gitkeep`

## O que não subir no GitHub
- `base_inteligente.db`
- arquivos pesados de partes, a menos que estejam fracionados de propósito em outro repositório
- exports gerados pelo usuário
- logs desnecessários

## Limitações conhecidas
- PDF escaneado pode exigir OCR opcional no deploy
- a camada atual é contextual e heurística; ainda não é busca vetorial semântica completa
- o sistema apoia análise técnica, mas não substitui advogado nem garante êxito
