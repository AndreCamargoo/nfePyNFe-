# azevedo_cloud/filters.py
import django_filters
from django.db.models import Q
from .models import Segmento


class SegmentoFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method='filter_search', label="Pesquisar")
    nome = django_filters.CharFilter(field_name='nome', lookup_expr='icontains')
    ano = django_filters.NumberFilter(field_name='ano', lookup_expr='exact')

    class Meta:
        model = Segmento
        fields = ['nome', 'ano', 'search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(nome__icontains=value) |
            Q(ano__icontains=value)
        )