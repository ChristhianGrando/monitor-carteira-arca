# Radar de Oportunidades ARCA

Este radar roda de hora em hora pelo GitHub Actions e envia Telegram apenas quando encontra alerta novo relevante.

Arquivos:
- `radar_oportunidades.py`: script do radar.
- `.github/workflows/radar-oportunidades.yml`: agendamento de hora em hora.
- `carteira.json`: valores manuais da carteira para cálculo de rebalanceamento.

Importante:
- É radar de estudo, não ordem de compra.
- Atualize `carteira.json` quando sua carteira mudar.
