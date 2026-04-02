"""
Constantes partilhadas do bolão (fusos horários e limites de regras de negócio).

- ``BR_TZ``: fuso *America/Sao_Paulo* para interpretar e mostrar datas/horas de jogos.
- ``MAX_BETS_PER_USER``: número máximo de palpites por utilizador Discord em cada bolão.
"""

from zoneinfo import ZoneInfo

BR_TZ = ZoneInfo("America/Sao_Paulo")
MAX_BETS_PER_USER = 2
