
from django.test import TestCase
from django.contrib.auth.models import User
from financial.models import Contract


class ContractTestCase(TestCase):
    def setUp(self) -> None:

        user = User.objects.create_user(
            username='test',
            email='test@test.com',
            password='123'
        )

        Contract.objects.create(
            name="test 1",
            value=0,
            value_open=0,
            value_closed=0,
            user=user
        )

        Contract.objects.create(
            name="test 2",
            value=100,
            value_open=0,
            value_closed=100,
            user=user
        )

    def test_contract_value_total(self):
        """Valor total = valor aberto + valor fechado"""
        test_1 = Contract.objects.get(name='test 1')
        test_2 = Contract.objects.get(name='test 2')

        self.assertEqual(test_1.value, (test_1.value_open + test_1.value_closed))
        self.assertEqual(test_2.value, (test_2.value_open + test_2.value_closed))
