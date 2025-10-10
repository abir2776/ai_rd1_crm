import logging

from django.contrib.auth.models import BaseUserManager
from django.utils import timezone

from common.choices import Status

logger = logging.getLogger(__name__)


class CustomUserManager(BaseUserManager):
    def _create_user(
        self, email, password, is_staff, is_superuser, is_active=True, **kwargs
    ):
        """
        Creates and saves a User with the given email and password.
        """
        now = timezone.now()
        if not email:
            raise ValueError("email must be set!")
        user = self.model(
            username=email,
            email=email,
            is_staff=is_staff,
            is_active=is_active,
            is_superuser=is_superuser,
            last_login=now,
            date_joined=now,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **kwargs):
        return self._create_user(email, password, False, False, **kwargs)

    def create_superuser(self, email, password, **kwargs):
        return self._create_user(email, password, True, True, **kwargs)

    def get_status_active(self):
        return self.get_queryset().filter(status=Status.ACTIVE, is_active=True)
