import json
import io
from unittest.mock import patch
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from facetexture.models import BDOClass, Character
from facetexture.views import get_bdo_class_image_url, get_bdo_class_symbol_url
from PIL import Image


class GetBDOClassSymbolURLTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        cls.client = Client()

        user = User.objects.create_user(username="test", email="test@test.com", password="123")

        user_2 = User.objects.create_user(username="test_2", email="test2@test.com", password="1234")

        bdo_class_warrior = BDOClass.objects.create(name="Warrior", abbreviation="Wr")
        bdo_class_witch = BDOClass.objects.create(name="Witch", abbreviation="Wt")
        BDOClass.objects.create(name="Arqueiro", abbreviation="Archer")

        Character.objects.create(
            user=user,
            name="witch2",
            show=False,
            bdoClass=bdo_class_witch,
            image="witch.png",
            order=3,
            upload=True,
        )

        Character.objects.create(
            user=user,
            name="witch1",
            show=True,
            bdoClass=bdo_class_witch,
            image="witch.png",
            order=2,
            upload=False,
        )

        Character.objects.create(
            user=user,
            name="witch3",
            show=False,
            bdoClass=bdo_class_witch,
            image="witch.png",
            order=4,
            upload=True,
            active=False,
        )

        Character.objects.create(
            user=user_2,
            name="warrior",
            show=True,
            bdoClass=bdo_class_warrior,
            image="warrior.png",
            order=1,
            upload=True,
        )

        Character.objects.create(
            user=user_2,
            name="witch",
            show=False,
            bdoClass=bdo_class_witch,
            image="witch.png",
            order=2,
            upload=True,
        )

        Character.objects.create(
            user=user,
            name="warrior",
            show=True,
            bdoClass=bdo_class_warrior,
            image="warrior.png",
            order=1,
            upload=True,
        )

        token = cls.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test", "password": "123"},
        )

        cls.token_json = json.loads(token.content)

    def setUp(self) -> None:
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer " + self.token_json["tokens"]["access"]

    @override_settings(BASE_URL="http://testserver")
    def test_get_bdo_class_symbol_url(self):
        class_id = 1
        expected_url = "http://testserver" + reverse("facetexture_get_symbol_class", args=[class_id])
        self.assertEqual(get_bdo_class_symbol_url(class_id), expected_url)

    @override_settings(BASE_URL="http://testserver")
    def test_get_bdo_class_image_url(self):
        class_id = 1
        expected_url = "http://testserver" + reverse("facetexture_get_image_class", args=[class_id])
        self.assertEqual(get_bdo_class_image_url(class_id), expected_url)

    @override_settings(BASE_URL="http://testserver")
    def test_get_bdo_class_image_url_with_different_id(self):
        class_id = 2
        expected_url = "http://testserver" + reverse("facetexture_get_image_class", args=[class_id])
        self.assertEqual(get_bdo_class_image_url(class_id), expected_url)

    @patch("facetexture.views.get_bdo_class_image_url")
    def test_get_facetexture_config(self, mock_get_bdo_class_image_url):
        class_image_url = "http://testserver/static/images/class_image.png"
        mock_get_bdo_class_image_url.return_value = class_image_url

        response = self.client.get("/facetexture/")
        response_body = json.loads(response.content)
        characters_data = response_body["characters"]
        self.assertEqual(characters_data.__len__(), 3)
        character_data = characters_data[0]
        self.assertEqual(character_data["name"], "warrior")
        self.assertEqual(character_data["show"], True)
        self.assertEqual(character_data["image"], "warrior.png")
        self.assertEqual(character_data["order"], 1)
        self.assertEqual(character_data["upload"], True)
        character_class_data = character_data["class"]
        self.assertEqual(character_class_data["name"], "Warrior")
        self.assertEqual(character_class_data["abbreviation"], "Wr")
        self.assertEqual(character_class_data["class_image"], class_image_url)

    @patch("facetexture.views.get_bdo_class_image_url")
    def test_get_bdo_class_sem_filtro(self, mock_get_bdo_class_image_url):
        class_image_url = "http://testserver/static/images/class_image.png"
        mock_get_bdo_class_image_url.return_value = class_image_url

        response = self.client.get("/facetexture/class")
        response_body = json.loads(response.content)
        class_data = response_body["class"]

        self.assertEqual(class_data.__len__(), 3)
        first_class_data = class_data[0]
        self.assertEqual(first_class_data["name"], "Arqueiro")
        self.assertEqual(first_class_data["abbreviation"], "Archer")
        self.assertEqual(first_class_data["class_image"], class_image_url)

    @patch("facetexture.views.get_bdo_class_image_url")
    def test_get_bdo_class_com_filtro(self, mock_get_bdo_class_image_url):
        class_image_url = "http://testserver/static/images/class_image.png"
        mock_get_bdo_class_image_url.return_value = class_image_url

        response = self.client.get("/facetexture/class", data={"id": 1})
        response_body = json.loads(response.content)
        class_data = response_body["class"]

        self.assertEqual(class_data.__len__(), 1)
        filtered_class_data = class_data[0]
        self.assertEqual(filtered_class_data["name"], "Warrior")
        self.assertEqual(filtered_class_data["abbreviation"], "Wr")
        self.assertEqual(filtered_class_data["class_image"], class_image_url)

    def test_preview_background_no_file(self):
        response = self.client.post("/facetexture/preview")

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"msg": "Nao existe nenhum background"})

    def test_preview_background_no_characters(self):
        Character.objects.all().delete()
        image = Image.new('RGB', (100, 100))
        image_file = io.BytesIO()
        image.save(image_file, format='PNG')
        image_file.seek(0)

        response = self.client.post(reverse('facetexture_preview_background'), {'background': image_file})

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"msg": "Facetexture nao encontrado"})

    def test_preview_background_success(self):
        image = Image.new('RGB', (1000, 1000))
        image_file = io.BytesIO()
        image.save(image_file, format='PNG')
        image_file.seek(0)

        response = self.client.post(reverse('facetexture_preview_background'), {'background': image_file})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')

    def test_download_background_no_file(self):
        response = self.client.post(reverse('facetexture_download_background'))

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"msg": "Nao existe nenhum background"})

    def test_download_background_no_characters(self):
        Character.objects.all().delete()
        image = Image.new('RGB', (100, 100))
        image_file = io.BytesIO()
        image.save(image_file, format='PNG')
        image_file.seek(0)

        response = self.client.post(reverse('facetexture_download_background'), {'background': image_file})

        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(response.content, {"msg": "Facetexture nao encontrado"})

    def test_download_background_success(self):
        image = Image.new('RGB', (1000, 1000))
        image_file = io.BytesIO()
        image.save(image_file, format='PNG')
        image_file.seek(0)

        response = self.client.post(reverse('facetexture_download_background'), {'background': image_file})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')