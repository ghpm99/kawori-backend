import time

from django.core.management.base import BaseCommand

from facetexture.models import BDOClass


class Command(BaseCommand):
    """
    Cadastrar a classe Wukong
    """

    def run_command(self):
        suggested_glow_colors = {
            1: "#8ee0b7",
            2: "#ff8880",
            3: "#80bfff",
            4: "#e090ff",
            5: "#c2d9ff",
            6: "#6080b0",
            7: "#6090ff",
            8: "#a0e0da",
            9: "#ff8088",
            10: "#90b0e0",
            11: "#a86a30",
            12: "#80c0ff",
            13: "#ff8080",
            14: "#d0c080",
            15: "#90e0c0",
            16: "#c08040",
            17: "#60a080",
            18: "#b0a0ff",
            19: "#ff8c8c",
            20: "#80e0ff",
            21: "#e0c080",
            22: "#FF4040",  # Ou "#FF8080" se preferir um vermelho mais suave para o brilho
            23: "#c0b0ff",
            24: "#80a0b0",
            25: "#a0a0ff",
            26: "#905040",
            27: "#ffc0f8",
            28: "#c2d9ff",
            29: "#d0a090",
            30: "#904040",
        }
        all_bdo_classes = BDOClass.objects.all()

        for bdo_class in all_bdo_classes:
            bdo_class.color = suggested_glow_colors.get(
                bdo_class.class_order, "#C0E0FF"
            )
            bdo_class.save()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
