import time
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    """
        Adiciona registro para migrar models
    """

    def run_command(self):

        migrations = [
            ['contract', '0001_initial', datetime.now()],
            ['invoice', '0001_initial', datetime.now()],
            ['payment', '0001_initial', datetime.now()],
            ['tag', '0001_initial', datetime.now()],
        ]

        for migration in migrations:
            query_migrations = """
                INSERT INTO django_migrations (app, name, applied)
                VALUES (%(app)s, %(name)s, %(applied)s);
            """
            with connection.cursor() as cursor:
                cursor.execute(query_migrations, {
                    'app': migration[0],
                    'name': migration[1],
                    'applied': migration[2],
                })

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
