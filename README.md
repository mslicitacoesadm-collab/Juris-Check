# DECIFRA Licitações — versão final pública

Sistema em Streamlit para auditoria de citações jurídicas em peças de licitação, com tela única, amostra gratuita, bloqueio premium e integração com Mercado Pago Checkout Pro.

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Base de dados

Esta entrega não inclui a base. Coloque seus arquivos `.db` em:

```text
data/base/
```

O sistema espera bases SQLite com tabela `acordaos`, como no projeto original.

## Configurar pagamento

No Streamlit Cloud, vá em **Settings > Secrets** e preencha:

```toml
DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande"
DECIFRA_APP_URL = "https://seu-app.streamlit.app"
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-..."
DECIFRA_NOTIFICATION_URL = ""
```

## Fluxo comercial

1. Usuário envia arquivo ou cola texto.
2. Sistema mostra amostra gratuita.
3. Relatório completo fica bloqueado.
4. Usuário paga pelo Mercado Pago.
5. Retorno aprovado libera o relatório.
6. Fallback manual por PIX/WhatsApp/código fica disponível.

## Observação

Para o Mercado Pago liberar automaticamente após o pagamento, o app precisa estar publicado em URL HTTPS e o `DECIFRA_APP_URL` precisa apontar para a URL pública do Streamlit.
