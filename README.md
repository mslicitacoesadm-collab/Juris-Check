# DECIFRA Licitações — versão final estratégica

Sistema Streamlit em tela única para auditoria de peças jurídicas com camada comercial.

## O que vem nesta versão
- Modo público `pagamento` ou `livre`, controlado por senha administrativa.
- Página principal única, sem excesso de telas.
- Prévia da peça com blur quando o relatório está bloqueado.
- Amostra gratuita limitada.
- Mercado Pago Checkout Pro.
- PIX/WhatsApp/código manual como fallback.
- Exportação DOCX, PDF e CSV no modo liberado.
- Sem base de dados incluída.

## Como usar
1. Coloque seus arquivos `.db` em `data/base/`.
2. Configure os secrets no Streamlit Cloud com base em `.streamlit/secrets.toml.example`.
3. Rode:
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Secrets principais
```toml
DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande"
DECIFRA_APP_URL = "https://seu-app.streamlit.app"
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-..."
DECIFRA_NOTIFICATION_URL = ""
DECIFRA_ADMIN_PASSWORD = "troque-senha-admin"
DECIFRA_DEFAULT_MODE = "pagamento"
```

## Modo administrativo
Abra a área administrativa na própria página, digite a senha e escolha:
- `pagamento`: libera apenas amostra grátis e exige checkout/código.
- `livre`: libera tudo para testes públicos, sem cobrança.

A escolha fica salva no arquivo `.decifra_mode.json` enquanto o app estiver rodando no ambiente.
