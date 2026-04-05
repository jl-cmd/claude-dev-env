"""Management command with DEBUG check in helper function - EDGE CASE: should be caught"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Test command with DEBUG check in helper"

    def _check_debug(self):
        if not settings.DEBUG:
            raise CommandError("This command can only be run in DEBUG mode")

    def handle(self, *args, **options):
        self._check_debug()
        print("Running in DEBUG mode")
        return "Success"
