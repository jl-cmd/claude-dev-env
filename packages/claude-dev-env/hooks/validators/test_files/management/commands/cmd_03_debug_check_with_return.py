"""Management command with DEBUG check using return - should NOT be caught"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test command with DEBUG check using return"

    def handle(self, *args, **options):
        if not settings.DEBUG:
            return "ERROR: This command requires DEBUG mode"

        print("Running in DEBUG mode")
        return "Success"
