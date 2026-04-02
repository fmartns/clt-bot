from django.db import models


class Bolao(models.Model):
    """Um bolão aberto por vez por servidor (discord_guild_id + closed=False)."""

    discord_guild_id = models.BigIntegerField(db_index=True)
    channel_id = models.BigIntegerField()
    message_id = models.BigIntegerField(default=0)
    team_home = models.CharField(max_length=255)
    team_away = models.CharField(max_length=255)
    match_at_display = models.CharField(max_length=512)
    prize = models.TextField(blank=True, null=True)
    closed = models.BooleanField(default=False, db_index=True)
    gols_casa_final = models.PositiveSmallIntegerField(null=True, blank=True)
    gols_visitante_final = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Bolão {self.pk} {self.team_home}×{self.team_away} ({'fechado' if self.closed else 'aberto'})"


class BolaoBet(models.Model):
    bolao = models.ForeignKey(Bolao, on_delete=models.CASCADE, related_name='bets')
    discord_user_id = models.BigIntegerField()
    username = models.CharField(max_length=80)
    prediction = models.CharField(max_length=32)
    team_pick = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self) -> str:
        return f"{self.username} {self.prediction}"
