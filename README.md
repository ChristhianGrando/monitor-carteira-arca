# Monitor Carteira ARCA - 2x ao dia, sem repetir notícia

Roda às 09:00 e 18:00 no horário do Brasil usando GitHub Actions.

O script:
- busca notícias via RSS/Google News;
- filtra notícias que já foram enviadas antes;
- classifica impacto;
- envia relatório completo no Telegram em partes;
- salva histórico em `relatorios/noticias_enviadas.json`.
