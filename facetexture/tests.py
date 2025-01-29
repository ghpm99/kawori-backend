import json
from unittest.mock import patch
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from facetexture.models import BDOClass, Character
from facetexture.views import get_bdo_class_image_url, get_bdo_class_symbol_url

class GetBDOClassSymbolURLTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        cls.client = Client()

        user = User.objects.create_user(username="test", email="test@test.com", password="123")

        character = Character.objects.create(
            user=user,
            name="Test Character",
            show=True,
            bdoClass=BDOClass.objects.create(name="Test Class", abbreviation="TC"),
            image="test.png",
            order=1,
            upload=True,
        )

        character.save()

        token = cls.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test", "password": "123"},
        )

        cls.token_json = json.loads(token.content)

    def setUp(self) -> None:
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer " + self.token_json["tokens"]["access"]

    @override_settings(BASE_URL='http://testserver')
    def test_get_bdo_class_symbol_url(self):
        class_id = 1
        expected_url = 'http://testserver' + reverse("facetexture_get_symbol_class", args=[class_id])
        self.assertEqual(get_bdo_class_symbol_url(class_id), expected_url)


    @override_settings(BASE_URL='http://testserver')
    def test_get_bdo_class_image_url(self):
        class_id = 1
        expected_url = 'http://testserver' + reverse("facetexture_get_image_class", args=[class_id])
        self.assertEqual(get_bdo_class_image_url(class_id), expected_url)


    @override_settings(BASE_URL='http://testserver')
    def test_get_bdo_class_image_url_with_different_id(self):
        class_id = 2
        expected_url = 'http://testserver' + reverse("facetexture_get_image_class", args=[class_id])
        self.assertEqual(get_bdo_class_image_url(class_id), expected_url)


    @patch('facetexture.views.get_bdo_class_image_url')
    def test_get_facetexture_config(self, mock_get_bdo_class_image_url):
        mock_get_bdo_class_image_url.return_value = 'http://testserver/static/images/class_image.png'

        response = self.client.get("/facetexture/")
        response_body = json.loads(response.content)
        characters_data = response_body["characters"]
        self.assertEqual(characters_data.__len__(), 1)