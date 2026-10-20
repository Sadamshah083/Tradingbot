"""Make the account with SUPERADMIN_EMAIL the one and only admin; demote every other staff/superuser.

    python manage.py ensure_superadmin
Runs on every start (run_portal.ps1), so nobody can quietly keep admin rights.
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Promote SUPERADMIN_EMAIL to the only superuser and demote all other staff accounts."

    def handle(self, *args, **options):
        User = get_user_model()
        email = settings.SUPERADMIN_EMAIL
        if not email:
            self.stdout.write(self.style.WARNING("SUPERADMIN_EMAIL is not set in .env - nothing changed."))
            return
        owner = User.objects.filter(email__iexact=email).first()
        password = os.getenv("SUPERADMIN_PASSWORD", "")
        if not owner:
            if not password:
                self.stdout.write(self.style.WARNING(f"No account with e-mail {email} yet. Register it first at /accounts/register/ (or set SUPERADMIN_PASSWORD in .env), then re-run."))
                return
            username = os.getenv("SUPERADMIN_USERNAME", "") or email.split("@")[0]
            owner = User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Created superadmin {username} <{email}>."))
        elif password and not owner.check_password(password):
            owner.set_password(password)   # .env is the source of truth for the owner password when it is set there
            owner.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("Superadmin password updated from SUPERADMIN_PASSWORD."))
        if not (owner.is_staff and owner.is_superuser and owner.is_active):
            owner.is_staff = owner.is_superuser = owner.is_active = True
            owner.save(update_fields=["is_staff", "is_superuser", "is_active"])
            self.stdout.write(self.style.SUCCESS(f"{owner.username} <{owner.email}> is now the superadmin."))
        others = User.objects.exclude(pk=owner.pk).filter(models_q_staff_or_super())
        n = others.count()
        if n:
            for u in others:
                self.stdout.write(f"  demoted: {u.username} <{u.email}>")
            others.update(is_staff=False, is_superuser=False)
        self.stdout.write(self.style.SUCCESS(f"Admin side restricted to {owner.username}; {n} other account(s) demoted."))


def models_q_staff_or_super():
    from django.db.models import Q
    return Q(is_staff=True) | Q(is_superuser=True)
