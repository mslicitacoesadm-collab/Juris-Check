# Validador de Autoridade Jurídica

## Solução adotada

A abordagem correta para o Streamlit Cloud é **não carregar vários JSONs diretamente no app**.

Em vez disso, este projeto usa:

- **1 banco SQLite por ano** em `data/base/`
- **FTS5 do SQLite** para busca textual rápida
- **consulta sob demanda**, sem carregar a base inteira em memória

Isso evita o erro clássico de boot quando a base JSON fica pesada demais.

## Estrutura esperada

```text
app.py
modules/
tools/
data/
  base/
    acordaos_2016.db
    acordaos_2017.db
    ...
```

## Como aplicar

### 1. Extraia sua base localmente
Seu arquivo atual está em `.rar`. O ideal é extrair no seu computador para uma pasta com os JSONs essenciais.

### 2. Gere os bancos SQLite por ano
No Windows, abra o terminal na pasta do projeto e rode:

```bash
python tools/build_year_dbs.py "CAMINHO_DOS_JSONS" "data/base"
```

Exemplo:

```bash
python tools/build_year_dbs.py "C:\base_json" "data\base"
```

### 3. Suba para o GitHub
Depois de gerar, suba os arquivos `acordaos_YYYY.db` para `data/base/`.

### 4. Publique no Streamlit
Aponte o deploy para `app.py`.

## Por que isso funciona melhor

- o app abre leve
- a base não é toda carregada em RAM
- a busca é feita direto no banco
- você evita dezenas de JSONs sendo processados no boot
- cada ano vira um arquivo mais organizado e mais previsível para deploy

## Observação importante

O Streamlit Cloud normalmente lida melhor com alguns `.db` bem organizados do que com dezenas de `.json` grandes carregados em memória.
