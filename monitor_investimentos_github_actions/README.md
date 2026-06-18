# Monitor gratuito de notícias da carteira ARCA/BTG

Este projeto roda um script Python que busca notícias em RSS/Google News, classifica impacto por palavras-chave e gera um relatório diário da carteira:

- IBOB11
- WRLD11
- SPCX34
- HGLG11
- KNCR11
- KNRI11
- CDB 100% CDI / Caixa

Ele não usa API paga de IA. A classificação é feita por regras e palavras-chave.

## Como rodar no computador

```bash
pip install -r requirements.txt
python monitor_investimentos.py
```

O relatório será criado na pasta `relatorios`.

## Como rodar grátis no GitHub Actions

1. Crie um repositório no GitHub.
2. Envie todos estes arquivos para o repositório.
3. Entre em **Actions** no GitHub.
4. Habilite workflows, se pedir.
5. O robô roda automaticamente de segunda a sexta às 18h do Brasil.
6. Você também pode rodar manualmente em **Actions > Monitor Carteira ARCA > Run workflow**.

## Envio opcional pelo Telegram

Sem Telegram, o relatório fica salvo no próprio repositório e também como artifact da Action.

Para receber no Telegram:

1. Crie um bot com o @BotFather.
2. Pegue o token.
3. Descubra seu chat_id.
4. No GitHub, vá em **Settings > Secrets and variables > Actions > New repository secret**.
5. Crie:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

Pronto. O resumo será enviado automaticamente.
