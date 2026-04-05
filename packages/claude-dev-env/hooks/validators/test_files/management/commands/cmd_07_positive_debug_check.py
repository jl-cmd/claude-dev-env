"""Management command with positive DEBUG check - EDGE CASE: check line 186-187 logic"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Test command with positive DEBUG check"

    def handle(self, *args, **options):
        if settings.DEBUG:
            print("Running in DEBUG mode")
        else:
            raise CommandError("This command can only be run in DEBUG mode")

        return "Success"
