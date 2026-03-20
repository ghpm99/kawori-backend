"""
Teste simples para verificar se as URLs estão funcionando
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse


class PaymentURLsTestCase(TestCase):
    def setUp(self):
        # Criar usuário para testes que precisam de autenticação
        self.user = User.objects.create_superuser(
            username="test", email="test@test.com", password="123"
        )
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(self.user)

    def test_get_all_scheduled_url_resolves(self):
        """Testa se a URL get_all_scheduled resolve corretamente"""
        try:
            url = reverse("financial_get_all_scheduled")
            print(f"URL resolvida: {url}")
            self.assertEqual(url, "/financial/payment/scheduled")
        except Exception as e:
            self.fail(f"Erro ao resolver URL financial_get_all_scheduled: {e}")

    def test_get_csv_mapping_url_resolves(self):
        """Testa se a URL get_csv_mapping resolve corretamente"""
        try:
            url = reverse("financial_get_csv_mapping")
            print(f"URL resolvida: {url}")
            self.assertEqual(url, "/financial/payment/csv-mapping/")
        except Exception as e:
            self.fail(f"Erro ao resolver URL financial_get_csv_mapping: {e}")

    def test_process_csv_upload_url_resolves(self):
        """Testa se a URL process_csv_upload resolve corretamente"""
        try:
            url = reverse("financial_process_csv_upload")
            print(f"URL resolvida: {url}")
            self.assertEqual(url, "/financial/payment/process-csv/")
        except Exception as e:
            self.fail(f"Erro ao resolver URL financial_process_csv_upload: {e}")

    def test_all_payment_urls_list(self):
        """Lista todas as URLs de payment para debug"""
        from django.urls import get_resolver
        from django.urls.resolvers import URLPattern, URLResolver

        def list_urls(urlpatterns, prefix=""):
            urls = []
            for pattern in urlpatterns:
                if isinstance(pattern, URLResolver):
                    urls.extend(
                        list_urls(pattern.url_patterns, prefix + str(pattern.pattern))
                    )
                elif isinstance(pattern, URLPattern):
                    urls.append(f"{prefix}{pattern.pattern} -> {pattern.name}")
            return urls

        resolver = get_resolver()
        urls = list_urls(resolver.url_patterns)
        print("\n=== URLs encontradas ===")
        for url in urls:
            if "payment" in url or "financial" in url:
                print(url)
