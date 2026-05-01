# DECIFRA Licitações — Versão Final Comercial

Sistema Streamlit para auditoria técnica de peças de licitação, validação de citações/acórdãos e entrega profissional ao cliente.

## O que esta versão entrega

- Página principal única, limpa e responsiva.
- Senha administrativa padrão: `Skcoqdra.4`.
- Painel administrativo para alternar entre modo livre e modo pagamento.
- Controle de preço, quantidade de resultados grátis, Mercado Pago, PIX, WhatsApp, código manual e blur da prévia.
- Prévia real da peça com blur para aumentar percepção de valor.
- Retorno mais verídico: o sistema mostra o que foi localizado, sugerido, validado e o que exige revisão jurídica.
- Download da peça marcada em DOCX.
- Download de relatório técnico em DOCX e PDF.
- Download de planilha CSV com todos os pontos da auditoria.
- Integração Mercado Pago Checkout Pro por criação de preferência.
- Sem base inclusa. Coloque seus arquivos `.db` em `data/base/`.

## Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Onde colocar a base

Coloque seus arquivos SQLite `.db` aqui:

```text
data/base/
```

O sistema não acompanha base de acórdãos nesta versão.

## Configuração no Streamlit Cloud

Em **Settings > Secrets**, configure:

```toml
DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande-e-secreta"
DECIFRA_APP_URL = "https://SEU-APP.streamlit.app"
DECIFRA_NOTIFICATION_URL = ""
DECIFRA_DEFAULT_MODE = "pagamento"
DECIFRA_FREE_LIMIT = 1
DECIFRA_BRAND_NAME = "DECIFRA Licitações"
DECIFRA_ADMIN_PASSWORD = "Skcoqdra.4"
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-..."
```

## Mercado Pago

Esta versão usa Checkout Pro via API `/checkout/preferences`.

Fluxo:

1. O usuário faz a auditoria.
2. O sistema gera um `order_id`.
3. O botão cria uma preferência no Mercado Pago.
4. O usuário paga no ambiente do Mercado Pago.
5. Ao voltar para o app, o sistema consulta `payment_id` e libera se estiver aprovado.

Para produção, configure `DECIFRA_APP_URL` com a URL pública HTTPS do Streamlit.

## Painel administrativo

Abra o expander **Administração da ferramenta** na tela principal e digite:

```text
Skcoqdra.4
```

Você poderá controlar:

- modo público: livre ou pagamento;
- preço;
- resultados gratuitos;
- blur da prévia;
- Mercado Pago ativo/inativo;
- fallback PIX/WhatsApp;
- código manual;
- busca rápida;
- geração de código de liberação para pedido atual.

## Observação jurídica

A ferramenta é apoio técnico. Ela não substitui revisão jurídica final antes do protocolo.
