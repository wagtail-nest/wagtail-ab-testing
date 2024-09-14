from io import StringIO

from django.core import management
from django.test import TestCase


class TestMigrations(TestCase):
    def test_migrations(self):
        output = StringIO()

        try:
            management.call_command(
                "makemigrations",
                "wagtail_ab_testing",
                "--check",
                stdout=output,
            )

        except SystemExit:
            self.fail(output.getvalue())
