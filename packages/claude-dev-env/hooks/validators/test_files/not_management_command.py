"""Regular file NOT in management/commands/ - should NOT be checked"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "This is not in management/commands/ directory"

    def handle(self, *args, **options):
        print("No DEBUG check needed")
        return "Success"
