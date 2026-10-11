from decimal import Decimal

from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum
from .models import Category, Expense, Budget 

class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer pour l'inscription d'un nouvel utilisateur.
    Valide username, email et password.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        read_only_fields = ['id']

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "Ce nom d'utilisateur existe déjà."
            )
        return value

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user 
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'date_joined')
        read_only_fields = ('id', 'date_joined')

    def validate_username(self, value):
        qs = User.objects.filter(username=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà utilisé.")
        return value

    def validate_email(self, value):
        if not value:
            return value
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user
            
            
class CategorySerializer(serializers.ModelSerializer):
    total_spent = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Category
        fields = ('id', 'name', 'icon', 'color', 'monthly_limit', 'total_spent', 'created_at')
        read_only_fields = ('id', 'created_at', 'total_spent')
        
    def get_total_spent(self, obj):
        if hasattr(obj, 'total_spent'):
            return obj.total_spent or 0
        from django.db.models import Sum
        from django.utils import timezone
        
        month = self.context.get('month')
        today = month or timezone.now().date()
        total = obj.expenses.filter(
            date__year=today.year,
            date__month=today.month
        ).aggregate(Sum('amount'))['amount__sum']
        return total or 0
    
    def validate_monthly_limit(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("La limite mensuelle doit être un nombre positif.")
        return value
    
class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    
    class Meta:
        model = Expense
        fields = ('id', 'amount', 'description', 'date', 'category', 'category_name', 'category_color', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        request = self.context.get('request')
        date_value = attrs.get('date') or getattr(self.instance, 'date', None)

        if request and request.user and date_value:
            month = date_value.replace(day=1)
            budget = Budget.objects.filter(user=request.user, month=month).first()

            if not budget:
                raise serializers.ValidationError(
                    'Ajoute d’abord un budget pour ce mois avant de créer une dépense.'
                )

            current_total = Expense.objects.filter(
                user=request.user,
                date__year=month.year,
                date__month=month.month,
            )

            if self.instance:
                current_total = current_total.exclude(pk=self.instance.pk)

            current_total = current_total.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            new_amount = attrs.get('amount', self.instance.amount if self.instance else Decimal('0.00'))

            if current_total + new_amount > budget.amount:
                raise serializers.ValidationError(
                    'Le budget mensuel est déjà entièrement utilisé.'
                )

        return attrs
        
    def validate_category(self, value):
        request = self.context.get('request')
        if request and value.user != request.user:
            raise serializers.ValidationError("Vous ne pouvez pas utiliser une catégorie qui ne vous appartient pas.")
        return value
    
class BudgetSerializer(serializers.ModelSerializer):
    total_expenses = serializers.SerializerMethodField(read_only=True)
    remaining = serializers.SerializerMethodField(read_only=True)
    percentage_used = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Budget
        fields = ('id', 'amount', 'month', 'total_expenses', 'remaining', 'percentage_used', 'created_at','updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at', 'total_expenses', 'remaining', 'percentage_used')
        
    def validate_month(self, value):
        return value.replace(day=1)

    def validate(self, attrs):
        request = self.context.get('request')
        month = attrs.get('month')
        if request and request.user and month:
            existing = Budget.objects.filter(user=request.user, month=month)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({
                    'non_field_errors': ['Un budget existe déjà pour ce mois.']
                })
        return attrs
    
    def _get_expenses_total(self, obj):
        from django.db.models import Sum
        total = Expense.objects.filter(
            user = obj.user,
            date__year=obj.month.year,
            date__month=obj.month.month
        ).aggregate(Sum('amount'))['amount__sum']
        return total or 0

    def get_total_expenses(self, obj):
        return self._get_expenses_total(obj)
    
    def get_remaining(self, obj):
        return obj.amount - self._get_expenses_total(obj)
    
    def get_percentage_used(self, obj):
        if obj.amount == 0:
            return 0
        return (self._get_expenses_total(obj) / obj.amount) * 100
    
    
class DashboardSerializer(serializers.Serializer):
    
    month = serializers.DateField()
    income = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_spent = serializers.DecimalField(max_digits=10, decimal_places=2)
    remaining = serializers.DecimalField(max_digits=10, decimal_places=2)
    spent_percentage = serializers.FloatField()
    categories = serializers.ListField(child=serializers.DictField())
    has_budget = serializers.BooleanField()     
