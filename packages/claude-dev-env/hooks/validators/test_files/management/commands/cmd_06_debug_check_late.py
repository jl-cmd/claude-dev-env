"""Management command with DEBUG check after 5 statements - EDGE CASE: might be caught or not"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Test command with late DEBUG check"

    def handle(self, *args, **options):
        stmt1 = "one"
        stmt2 = "two"
        stmt3 = "three"
        stmt4 = "four"
        stmt5 = "five"
        stmt6 = "six"

        # DEBUG check on statement 8 (beyond first 5)
        if not settings.DEBUG:
            raise CommandError("This command can only be run in DEBUG mode")

        print("Running in DEBUG mode")
        return "Success"
