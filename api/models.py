from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, RegexValidator
from decimal import Decimal

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=50)
    icon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        default='tag',
    )
    color = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        validators=[RegexValidator(
            regex=r'^#[0-9A-Fa-f]{6}$',
            message="La couleur doit être au format hexadécimal (#RRGGBB)"
        )],
        help_text="Couleur hexadécimale (ex: #FF5733)"
    )
    monthly_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Plafond mensuel optionnel pour cette catégorie (en Ar)"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')
        ordering = ['name']
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'

    def __str__(self):
        limit = f" [max {self.monthly_limit}Ar]" if self.monthly_limit else ""
        return f"{self.name}{limit} ({self.user.username})"
    

class Expense(models.Model):
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField(db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='expenses'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
        ]
        verbose_name = 'Dépense'
        verbose_name_plural = 'Dépenses'

    def __str__(self):
        return f"{self.amount}Ar - {self.category.name} ({self.date})"
    
class Budget(models.Model):
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Salaire / revenu du mois (en Ar)"
    )
    month = models.DateField(
        help_text="Toujours le 1er jour du mois (ex: 2026-09-01)"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'month')
        ordering = ['-month']
        verbose_name = 'Budget mensuel'
        verbose_name_plural = 'Budgets mensuels'

    def __str__(self):
        return f"{self.month.strftime('%m/%Y')} : {self.amount}Ar ({self.user.username})"