# JuriScan

Validador de citações e precedentes para peças jurídicas, com foco em recursos, impugnações e contrarrazões em licitações públicas.

## Fluxo do produto

1. Enviar peça jurídica em PDF, DOCX ou TXT.
2. Auditar citações.
3. Mostrar 1 resultado grátis.
4. Bloquear o restante com paywall visual.
5. Liberar relatório completo via código/token, sem login.

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Variáveis recomendadas

Configure no Streamlit Cloud em **Secrets** ou como variável de ambiente:

```toml
JURISCAN_ADMIN_PASSWORD="sua-senha-admin-forte"
JURISCAN_PAYMENT_URL="https://link.mercadopago.com.br/seu-link"
JURISCAN_MAX_UPLOAD_MB="20"
```

> A senha administrativa não deve ficar escrita no código. O app só libera o painel se `JURISCAN_ADMIN_PASSWORD` estiver configurada.

## Pagamento real

Esta versão já está pronta para o fluxo sem login por token:

- pagamento aprovado no Mercado Pago;
- webhook ou rotina externa chama a geração de token;
- usuário informa o código `JS-XXXX-XXXX-XXXX`;
- o relatório completo é liberado na sessão.

Para teste, o admin pode gerar tokens no painel administrativo.

## LGPD e segurança mínima

- Defina limite de upload.
- Use HTTPS no deploy.
- Não exponha a pasta `data/base` publicamente fora do app.
- Oriente o usuário a remover dados sensíveis desnecessários.
- Tokens e logs ficam em `runtime/juriscan_tokens.sqlite3`.

## Estrutura

- `app.py`: interface principal do JuriScan.
- `modules/search_engine.py`: motor de busca e validação.
- `modules/license_manager.py`: tokens, liberação e painel comercial.
- `data/base/`: bases SQLite locais.
