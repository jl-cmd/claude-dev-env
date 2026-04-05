"""Management command with proper DEBUG check - should NOT be caught"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Test command with proper DEBUG check"

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("This command can only be run in DEBUG mode")

        print("Running in DEBUG mode")
        return "Success"
