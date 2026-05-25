# JuriScan — Versão Final de Lançamento

Validador de citações e precedentes para peças jurídicas, com foco em recursos, impugnações e contrarrazões em licitações públicas.

## O que esta versão entrega

- Tela única e profissional, sem aparência de painel técnico.
- Fluxo claro: enviar peça → auditar → ver 1 resultado grátis → liberar relatório completo.
- Comparação lado a lado entre a citação usada na peça e a leitura técnica do JuriScan.
- Grau de confiança e legenda de status: validada, revisar tese, não localizada e correção sugerida.
- Relatório completo com exportação em DOCX, DOCX marcado, PDF e CSV.
- Paywall sem login, com liberação por código/token.
- Busca manual por número, ano ou tese jurídica.
- Painel administrativo protegido por variável de ambiente.
- Textos revisados para transmitir transparência, segurança e responsabilidade jurídica.

## Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configuração no Streamlit Cloud

Em **Settings → Secrets**, configure:

```toml
JURISCAN_ADMIN_PASSWORD = "sua-senha-administrativa"
JURISCAN_PAYMENT_URL = "https://link-do-mercado-pago-ou-checkout"
JURISCAN_MAX_UPLOAD_MB = "20"
JURISCAN_PRICE_LABEL = "R$ 29,90"
```

A senha administrativa não deve ficar fixa no código.

## Base de dados

Coloque os arquivos `.db` em:

```text
data/base/
```

A base não é exibida ao usuário final.

## Liberação do relatório completo

Sem integração por webhook, o administrador pode gerar códigos no painel interno.
Com Mercado Pago, o fluxo recomendado é:

1. Pagamento aprovado.
2. Webhook chama rotina de geração de token.
3. Token é entregue ao cliente.
4. Cliente informa o token e libera o relatório completo.

## Aviso jurídico

O JuriScan é uma ferramenta auxiliar de auditoria. O relatório não substitui a conferência da fonte oficial nem a revisão técnica do profissional responsável antes do protocolo.
