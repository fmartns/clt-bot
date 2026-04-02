from django.contrib import admin
from bolao.models import Bolao, BolaoBet


class BolaoBetInline(admin.TabularInline):
    model = BolaoBet
    extra = 0


@admin.register(Bolao)
class BolaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'team_home', 'team_away', 'discord_guild_id', 'closed', 'created_at')
    list_filter = ('closed',)
    inlines = [BolaoBetInline]
