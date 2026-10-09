from django.contrib import admin
from .models import Category, Expense, Budget

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'color', 'monthly_limit', 'created_at')
    list_filter = ('user',)
    search_fields = ('name',)
    ordering = ('name',)
    list_editable = ('monthly_limit',)       


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'amount', 'category', 'user', 'description')
    list_filter = ('category', 'date', 'user')
    search_fields = ('description',)
    date_hierarchy = 'date'
    ordering = ('-date',)
    autocomplete_fields = ('category',)


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('month', 'amount', 'user', 'created_at')
    list_filter = ('month', 'user')
    ordering = ('-month',)
    date_hierarchy = 'month'