from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from bolao.models import Bolao, BolaoBet

MAX_BETS_PER_USER = 2


def _serialize_bet(b: BolaoBet) -> dict:
    return {
        'user_id': b.discord_user_id,
        'username': b.username,
        'prediction': b.prediction,
        'team_pick': b.team_pick or '',
    }


def _serialize_bolao(b: Bolao) -> dict:
    return {
        'id': b.pk,
        'message_id': b.message_id,
        'channel_id': b.channel_id,
        'team_home': b.team_home,
        'team_away': b.team_away,
        'match_at_display': b.match_at_display,
        'prize': b.prize or None,
        'closed': b.closed,
        'bets': [_serialize_bet(x) for x in b.bets.all()],
    }


class BolaoCurrentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        guild_id = request.query_params.get('guild_id')
        if not guild_id:
            return Response({'error': 'guild_id is required'}, status=400)
        try:
            gid = int(guild_id)
        except ValueError:
            return Response({'error': 'invalid guild_id'}, status=400)
        bolao = Bolao.objects.filter(discord_guild_id=gid, closed=False).first()
        if bolao is None:
            return Response({'active': None}, status=200)
        return Response({'active': _serialize_bolao(bolao)}, status=200)


class BolaoStartView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        required = ('discord_guild_id', 'channel_id', 'team_home', 'team_away', 'match_at_display')
        for k in required:
            if not data.get(k):
                return Response({'error': f'{k} is required'}, status=400)
        gid = int(data['discord_guild_id'])
        if Bolao.objects.filter(discord_guild_id=gid, closed=False).exists():
            return Response({'error': 'Já existe um bolão aberto para este servidor.'}, status=400)
        prize = data.get('prize')
        if prize is not None and isinstance(prize, str):
            prize = prize.strip() or None
        b = Bolao.objects.create(
            discord_guild_id=gid,
            channel_id=int(data['channel_id']),
            message_id=0,
            team_home=str(data['team_home'])[:255],
            team_away=str(data['team_away'])[:255],
            match_at_display=str(data['match_at_display'])[:512],
            prize=prize,
        )
        return Response(_serialize_bolao(b), status=201)


class BolaoMessageView(APIView):
    permission_classes = [AllowAny]

    def patch(self, request, pk):
        mid = request.data.get('message_id')
        if mid is None:
            return Response({'error': 'message_id is required'}, status=400)
        bolao = get_object_or_404(Bolao, pk=pk, closed=False)
        bolao.message_id = int(mid)
        bolao.save(update_fields=['message_id'])
        return Response(_serialize_bolao(bolao), status=200)


class BolaoBetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        bolao = get_object_or_404(Bolao, pk=pk, closed=False)
        data = request.data
        for k in ('discord_user_id', 'username', 'prediction'):
            if k not in data:
                return Response({'error': f'{k} is required'}, status=400)
        if not str(data.get('username', '')).strip():
            return Response({'error': 'username is required'}, status=400)
        uid = int(data['discord_user_id'])
        n = BolaoBet.objects.filter(bolao=bolao, discord_user_id=uid).count()
        if n >= MAX_BETS_PER_USER:
            return Response(
                {'error': f'Máximo de {MAX_BETS_PER_USER} apostas por utilizador.'},
                status=400,
            )
        BolaoBet.objects.create(
            bolao=bolao,
            discord_user_id=uid,
            username=str(data['username'])[:80],
            prediction=str(data['prediction'])[:32],
            team_pick=str(data.get('team_pick') or '')[:120],
        )
        bolao.refresh_from_db()
        return Response(_serialize_bolao(Bolao.objects.prefetch_related('bets').get(pk=bolao.pk)), status=201)


def _dedupe_winners(winners_raw: list[BolaoBet]) -> list[dict]:
    seen: set[int] = set()
    out: list[dict] = []
    for b in winners_raw:
        if b.discord_user_id in seen:
            continue
        seen.add(b.discord_user_id)
        out.append({'discord_user_id': b.discord_user_id, 'username': b.username})
    return out


class BolaoCloseView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, pk):
        bolao = get_object_or_404(Bolao, pk=pk, closed=False)
        try:
            gc = int(request.data['gols_casa'])
            gv = int(request.data['gols_visitante'])
        except (KeyError, TypeError, ValueError):
            return Response({'error': 'gols_casa e gols_visitante são obrigatórios (inteiros).'}, status=400)
        if not (0 <= gc <= 20 and 0 <= gv <= 20):
            return Response({'error': 'Golos entre 0 e 20.'}, status=400)

        target = f'{gc}x{gv}'.lower()
        winners_qs = [
            b for b in bolao.bets.all()
            if b.prediction.strip().lower() == target
        ]
        winners = _dedupe_winners(winners_qs)

        bolao.closed = True
        bolao.gols_casa_final = gc
        bolao.gols_visitante_final = gv
        bolao.closed_at = timezone.now()
        bolao.save()

        return Response(
            {
                'team_home': bolao.team_home,
                'team_away': bolao.team_away,
                'prize': bolao.prize,
                'gols_casa_final': gc,
                'gols_visitante_final': gv,
                'winners': winners,
            },
            status=200,
        )
