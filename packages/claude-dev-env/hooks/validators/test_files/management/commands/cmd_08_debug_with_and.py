"""Management command with DEBUG and other condition - EDGE CASE: might not be caught"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Test command with DEBUG AND condition"

    def handle(self, *args, **options):
        if not settings.DEBUG and True:
            raise CommandError("This command can only be run in DEBUG mode")

        print("Running")
        return "Success"
