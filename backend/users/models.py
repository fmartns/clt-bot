from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='users_user_set',
        related_query_name='users_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='users_user_permissions',
        related_query_name='users_user',
    )

    discord_id = models.CharField(max_length=255, unique=True)
    discord_username = models.CharField(max_length=255)
    habbo_id = models.CharField(max_length=255, unique=True)
    habbo_username = models.CharField(max_length=255)
    habbo_user_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username

class HabboVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    habbo_name = models.CharField(max_length=255)
    verification_code = models.CharField(max_length=255)
    verification_expiry = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username