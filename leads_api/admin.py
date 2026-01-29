from django.contrib import admin
from .models import Company, Product, Event, Lead, Contact


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 1


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'cidade', 'estado', 'classificacao', 'created_at')
    search_fields = ('empresa', 'cnpj')
    list_filter = ('classificacao', 'estado', 'segmento')
    inlines = [ContactInline]


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('nome', 'created_at')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('nome', 'empresa_grupo')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data')
