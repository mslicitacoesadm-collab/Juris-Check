# DECIFRA Licitações — Versão Final Comercial

Esta versão foi ajustada para venda rápida em uma única página:

- tela principal única, sem sidebar obrigatória;
- design premium e mais limpo;
- análise grátis com amostra;
- bloqueio do relatório completo;
- exportação premium em DOCX, PDF e CSV;
- pagamento por Mercado Pago Checkout Pro;
- liberação automática por retorno de pagamento aprovado;
- liberação manual por código, como fallback para PIX/WhatsApp.

## Como publicar no Streamlit

1. Envie a pasta para o GitHub.
2. Publique o `app.py` no Streamlit Cloud.
3. Configure os secrets no painel do Streamlit.

```toml
DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande-e-secreta"
DECIFRA_APP_URL = "https://SEU-APP.streamlit.app"
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-..."
DECIFRA_NOTIFICATION_URL = ""
DECIFRA_CHECKOUT_URL = ""
```

## Mercado Pago

O app usa Checkout Pro. Ao clicar em “Gerar pagamento Mercado Pago”, o sistema cria uma preferência de pagamento usando o Access Token. Após pagamento aprovado, o Mercado Pago retorna para o app com `payment_id`/`collection_id`; o sistema consulta o pagamento na API e libera o Premium se estiver aprovado.

Para venda imediata, mantenha também o PIX/WhatsApp e use o código interno do pedido como fallback.

## Comando local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Observação importante

Para confirmação 100% robusta em produção, o ideal é usar também uma `notification_url` HTTPS com webhook/IPN. O Streamlit puro não é o ambiente ideal para receber webhooks complexos, mas o retorno com verificação de `payment_id` já permite automação funcional para MVP.
