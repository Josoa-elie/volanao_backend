from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from .models import Category, Expense, Budget
from .serializers import (
    RegisterSerializer,
    CategorySerializer,
    ExpenseSerializer,
    BudgetSerializer,
    DashboardSerializer,
)
from .permissions import IsOwner


# ─────────────────────────────────────────────────────
#  AUTH — REGISTER
# ─────────────────────────────────────────────────────
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return Response(
            {
                'detail': 'Utilisez POST pour créer un compte.',
                'method': 'POST',
                'endpoint': '/api/auth/register/'
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

class CategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les catégories de l'utilisateur connecté.
    
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        #Filtre par user → chaque user ne voit que ses catégories
        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        #Injection du user côté serveur (le front ne peut PAS le définir)
        serializer.save(user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # On transmet le mois pour le calcul de total_spent
        month_param = self.request.query_params.get('month')
        if month_param:
            try:
                context['month'] = datetime.strptime(month_param, '%Y-%m').date()
            except ValueError:
                pass
        return context

class ExpenseViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les dépenses de l'utilisateur connecté.
    """
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        qs = Expense.objects.filter(user=self.request.user)

        # Filtre par mois
        month = self.request.query_params.get('month')
        if month:
            try:
                m = datetime.strptime(month, '%Y-%m').date()
                qs = qs.filter(date__year=m.year, date__month=m.month)
            except ValueError:
                pass

        # Filtre par catégorie
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category_id=category)

        # Filtre par plage de dates
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        return qs.select_related('category')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class BudgetViewSet(viewsets.ModelViewSet):
    """
    CRUD sur le salaire mensuel de l'utilisateur connecté.
    Un seul budget par mois (contrainte unique_together).
    """
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        qs = Budget.objects.filter(user=self.request.user)

        month = self.request.query_params.get('month')
        if month:
            try:
                m = datetime.strptime(month, '%Y-%m').date()
                qs = qs.filter(month__year=m.year, month__month=m.month)
            except ValueError:
                pass

        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ─────────────────────────────────────────────────────
#  DASHBOARD (stats du mois)
# ─────────────────────────────────────────────────────
class DashboardView(APIView):
    """
    Stats complètes pour un mois donné.
    
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Récupère le mois demandé, ou mois en cours par défaut
        month_param = request.query_params.get('month')
        if month_param:
            try:
                month = datetime.strptime(month_param, '%Y-%m').date().replace(day=1)
            except ValueError:
                return Response(
                    {'error': "Format de mois invalide. Utilisez YYYY-MM."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            today = timezone.now().date()
            month = today.replace(day=1)

        # Budget du mois
        budget = Budget.objects.filter(user=user, month=month).first()
        income = budget.amount if budget else Decimal('0.00')

        # Total dépensé
        total_spent = Expense.objects.filter(
            user=user,
            date__year=month.year,
            date__month=month.month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Reste
        remaining = income - total_spent if budget else Decimal('0.00')

        # % dépensé
        spent_percentage = float((total_spent / income) * 100) if income > 0 else 0.0

        # Catégories avec leur total dépensé ce mois
        categories = Category.objects.filter(user=user)
        categories_data = CategorySerializer(
            categories,
            many=True,
            context={'month': month}
        ).data

        # Sérialisation finale
        dashboard_data = {
            'user' : user,
            'month': month,
            'income': income,
            'total_spent': total_spent,
            'remaining': remaining,
            'spent_percentage': round(spent_percentage, 2),
            'has_budget': budget is not None,
            'categories': categories_data,
        }

        serializer = DashboardSerializer(dashboard_data)
        return Response(serializer.data)