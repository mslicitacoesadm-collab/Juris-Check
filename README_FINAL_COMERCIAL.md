# DECIFRA Licitações — Versão Estável Final

Versão de página única, responsiva e pronta para público.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configurar no Streamlit Cloud

Crie/edite `.streamlit/secrets.toml`:

```toml
DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande"
DECIFRA_APP_URL = "https://seu-app.streamlit.app"
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-..."
DECIFRA_NOTIFICATION_URL = ""
```

## Mercado Pago

A integração cria uma preferência no Checkout Pro e consulta o status no retorno pelo `payment_id`/`collection_id`. Para produção, use URL HTTPS em `DECIFRA_APP_URL`.

## Fluxo comercial

1. Cliente envia DOCX/PDF/TXT ou cola texto.
2. Sistema libera uma amostra grátis.
3. Resultado completo, teses e downloads ficam bloqueados.
4. Cliente paga pelo Mercado Pago ou PIX/manual.
5. Pagamento aprovado libera automaticamente quando o Mercado Pago retorna com `payment_id`.
6. Operador pode liberar manualmente pelo código no menu lateral.
