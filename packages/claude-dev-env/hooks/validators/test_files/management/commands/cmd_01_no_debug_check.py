"""Management command with NO DEBUG check - SHOULD BE CAUGHT"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test command without DEBUG check"

    def handle(self, *args, **options):
        print("Running without DEBUG check")
        return "Success"
