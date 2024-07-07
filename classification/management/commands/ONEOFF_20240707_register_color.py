import time
from django.core.management.base import BaseCommand
from facetexture.models import BDOClass


class Command(BaseCommand):
    """
    Register colors in Bdo Class
    """

    def run_command(self):
        colors = [
            {'id': 0, 'color': '#4d8e66'},
            {"id": 1, "color": "#4d8e66"},
            {"id": 2, "color": "#bc433b"},
            {"id": 3, "color": "#3f7398"},
            {"id": 4, "color": "#a166b9"},
            {"id": 5, "color": "#92abe4"},
            {"id": 6, "color": "#243852"},
            {"id": 7, "color": "#314f97"},
            {"id": 8, "color": "#689a94"},
            {"id": 9, "color": "#a64047"},
            {"id": 10, "color": "#506ba4"},
            {"id": 11, "color": "#6e3913"},
            {"id": 12, "color": "#4c8ec0"},
            {"id": 13, "color": "#bf3e3e"},
            {"id": 14, "color": "#998758"},
            {"id": 15, "color": "#52a98d"},
            {"id": 16, "color": "#875023"},
            {"id": 17, "color": "#245237"},
            {"id": 18, "color": "#7f69e1"},
            {"id": 19, "color": "#cc4d4d"},
            {"id": 20, "color": "#43b5ca"},
            {"id": 21, "color": "#a9844e"},
            {"id": 22, "color": "#5f0000"},
            {"id": 23, "color": "#8b76d7"},
            {"id": 24, "color": "#4a6272"},
            {"id": 25, "color": "#767ae9"},
            {"id": 27, "color": "#522824"},
            {"id": 26, "color": "#ffa8ef"},
            {"id": 28, "color": "#92abe4"},
        ]

        bdo_class_list = BDOClass.objects.all()

        for classe in bdo_class_list:
            classe.color = colors[classe.id]['color']
            classe.save()

        print("Cores registradas!")

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
