"""Management command using imported DEBUG - EDGE CASE: should be caught (wrong pattern)"""
from django.conf import settings, DEBUG
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Test command with imported DEBUG"

    def handle(self, *args, **options):
        if not DEBUG:
            raise CommandError("This command can only be run in DEBUG mode")

        print("Running in DEBUG mode")
        return "Success"
