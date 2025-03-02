import time
from django.core.management.base import BaseCommand
from facetexture.models import BDOClass
from django.contrib.auth.models import User, Group


class Command(BaseCommand):
    """
    Register colors in Bdo Class
    """

    def run_command(self):
        print("Buscando grupo")
        group = Group.objects.filter(name="user")

        if group.exists() is False:
            print("Grupo nao encontrado")
            group = Group.objects.create(name="user")
            print("Grupo criado")

        print("Listando usuarios")
        user_list = User.objects.exclude(groups__name="user")

        print(f"Total de usuarios encontrados: {user_list.__len__()}")
        for user in user_list:
            print("Adicionando usuario ao grupo")
            group.user_set.add(user)

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
