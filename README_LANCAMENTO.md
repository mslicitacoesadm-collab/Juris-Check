# DECIFRA Licitações — versão pronta para vender

## O que foi adicionado
- Landing dentro do Streamlit com promessa comercial forte.
- Modo grátis com amostra do resultado.
- Paywall simples por documento.
- Pedido automático `DEC-...`.
- Código de liberação por HMAC, sem login e sem banco externo.
- Exportação premium: DOCX limpo, DOCX marcado, PDF e CSV.
- Busca manual limitada no grátis e completa no premium.

## Como configurar no Streamlit Cloud
Crie o arquivo `.streamlit/secrets.toml` ou use o painel de Secrets:

```toml
DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande-e-secreta"
DECIFRA_CHECKOUT_URL = ""
```

## Como liberar um cliente
1. O cliente analisa o documento e recebe um pedido tipo `DEC-XXXXXXXXXX`.
2. Ele paga via PIX ou checkout.
3. Você copia o código técnico exibido na tela do pedido e envia para o cliente.
4. O cliente cola na sidebar e libera os downloads.

> Depois, você pode esconder o código técnico da tela e gerar internamente em uma pequena área admin. Para vender rápido, deixei visível para facilitar testes.

## Preço recomendado
- Lançamento: R$ 9,90 a R$ 19,90.
- Após validação: R$ 29,90 a R$ 49,90 por documento.
- Serviço manual premium: R$ 97,00 a R$ 197,00 por revisão jurídica assistida.
