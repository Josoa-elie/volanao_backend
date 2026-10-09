from datetime import date

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Budget, Category, Expense


class ApiRootTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rootuser', password='secret123')
        self.client.force_authenticate(user=self.user)

    def test_api_root_returns_200(self):
        response = self.client.get(reverse('api-root'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('budgets', response.data)


class BudgetDuplicateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret123')
        self.client.force_authenticate(user=self.user)

    def test_cannot_create_second_budget_for_same_month(self):
        first = Budget.objects.create(user=self.user, amount=250000, month=date(2026, 9, 1))
        self.assertIsNotNone(first)

        response = self.client.post(
            reverse('budget-list'),
            {'amount': 300000, 'month': '2026-09-01'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Un budget existe déjà pour ce mois.', response.data['non_field_errors'][0])


class CategoryIconTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bob', password='secret123')
        self.client.force_authenticate(user=self.user)

    def test_category_icon_is_saved_and_returned(self):
        response = self.client.post(
            reverse('category-list'),
            {'name': 'Transport', 'icon': 'car', 'color': '#3498DB', 'monthly_limit': '150000'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['icon'], 'car')
        self.assertTrue(Category.objects.filter(user=self.user, name='Transport', icon='car').exists())


class ExpenseBudgetValidationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='charlie', password='secret123')
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(
            user=self.user,
            name='Alimentation',
            color='#FF5733',
        )

    def test_cannot_create_expense_without_budget_for_the_month(self):
        response = self.client.post(
            reverse('expense-list'),
            {
                'amount': '2500',
                'description': 'Courses',
                'date': '2026-10-12',
                'category': self.category.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Ajoute d’abord un budget pour ce mois avant de créer une dépense.', response.data['non_field_errors'][0])
        self.assertFalse(Expense.objects.filter(user=self.user, description='Courses').exists())

    def test_cannot_create_expense_when_budget_is_exhausted(self):
        Budget.objects.create(user=self.user, amount=5000, month=date(2026, 10, 1))
        Expense.objects.create(
            user=self.user,
            category=self.category,
            amount=5000,
            description='Déjà dépensé',
            date=date(2026, 10, 15),
        )

        response = self.client.post(
            reverse('expense-list'),
            {
                'amount': '1',
                'description': 'Dépense impossible',
                'date': '2026-10-20',
                'category': self.category.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Le budget mensuel est déjà entièrement utilisé.', response.data['non_field_errors'][0])
        self.assertFalse(Expense.objects.filter(user=self.user, description='Dépense impossible').exists())
