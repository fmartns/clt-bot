import unicodedata

from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from users.constants import VERIFICATION_LIFETIME
from users.models import User, HabboVerification
from users.services.habbo import HabboService
from users.services.verification_words import random_verification_word
from django.utils import timezone
from rest_framework.permissions import AllowAny


def _normalize_motto(text: str) -> str:
    """Compara motto do Habbo com o código sem depender de maiúsculas/acentos."""
    if text is None:
        return ''
    text = unicodedata.normalize('NFD', str(text).strip())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.upper()


class HabboVerificationView(APIView):

    permission_classes = [AllowAny]

    @extend_schema(
        summary='Verify a Habbo user',
        description='Verify a Habbo user',
    )
    def post(self, request):

        discord_id = request.data.get('discord_id')
        habbo_name = request.data.get('habbo_name')

        if not discord_id:
            return Response({'error': 'Discord ID is required'}, status=400)

        if not habbo_name:
            return Response({'error': 'Habbo name is required'}, status=400)

        discord_id = str(discord_id)
        discord_username = str(request.data.get('discord_username', discord_id))[:255]

        user, created = User.objects.get_or_create(
            discord_id=discord_id,
            defaults={
                'username': discord_id[:150],
                'discord_username': discord_username,
                'habbo_id': f'pending_{discord_id}'[:255],
                'habbo_username': habbo_name[:255],
            },
        )

        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])

        if user.habbo_user_verified:
            return Response(
                {'success': 'Habbo user verified', 'already_verified': True},
                status=200,
            )

        habbo_service = HabboService()

        habbo_response = habbo_service.get_user_info(habbo_name)

        if habbo_response.status_code != 200:
            return Response({'error': 'Habbo user not found'}, status=404)

        try:
            habbo_payload = habbo_response.json()
            habbo_motto = habbo_payload['motto']
        except (ValueError, KeyError, TypeError):
            return Response({'error': 'Invalid Habbo API response'}, status=502)

        verification = HabboVerification.objects.filter(user=user).first()

        if verification and verification.verification_expiry > timezone.now():
            if _normalize_motto(verification.verification_code) == _normalize_motto(habbo_motto):
                user.habbo_user_verified = True
                user.habbo_username = verification.habbo_name[:255]
                user.save(update_fields=['habbo_user_verified', 'habbo_username'])
                verification.delete()
                return Response({'success': 'Habbo user verified'}, status=200)
            return Response(
                {
                    'error': 'Verification code is incorrect',
                    'verification_code': verification.verification_code,
                },
                status=400,
            )
        else:
            if verification:
                verification.delete()

            verification_code = random_verification_word()

            HabboVerification.objects.create(
                user=user,
                habbo_name=habbo_name,
                verification_code=verification_code,
                verification_expiry=timezone.now() + VERIFICATION_LIFETIME,
            )

            return Response({'motto': habbo_motto, 'verification_code': verification_code}, status=200)


class RefreshVerificationWordView(APIView):
    """Gera nova palavra secreta mantendo a verificação pendente (mesmo nick Habbo)."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary='Refresh verification word',
        description='Replace the pending verification code with a new word (same 5-minute window reset).',
    )
    def post(self, request):
        discord_id = request.data.get('discord_id')
        habbo_name = request.data.get('habbo_name')

        if not discord_id:
            return Response({'error': 'Discord ID is required'}, status=400)
        if not habbo_name:
            return Response({'error': 'Habbo name is required'}, status=400)

        discord_id = str(discord_id)
        habbo_name = habbo_name.strip()
        if not habbo_name:
            return Response({'error': 'Habbo name is required'}, status=400)

        try:
            user = User.objects.get(discord_id=discord_id)
        except User.DoesNotExist:
            return Response({'error': 'No pending verification'}, status=400)

        if user.habbo_user_verified:
            return Response({'error': 'User already verified'}, status=400)

        verification = HabboVerification.objects.filter(user=user).first()
        if not verification:
            return Response({'error': 'No pending verification'}, status=400)

        if verification.verification_expiry <= timezone.now():
            verification.delete()
            return Response({'error': 'Verification expired'}, status=400)

        if verification.habbo_name.strip().lower() != habbo_name.lower():
            return Response({'error': 'Habbo name does not match pending verification'}, status=400)

        verification.verification_code = random_verification_word()
        verification.verification_expiry = timezone.now() + VERIFICATION_LIFETIME
        verification.save(update_fields=['verification_code', 'verification_expiry'])

        return Response({'verification_code': verification.verification_code}, status=200)