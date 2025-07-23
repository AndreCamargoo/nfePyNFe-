import django_filters
from django.db.models import Q
from .models import NotaFiscal, Produto, Emitente


class NotaFiscalFilter(django_filters.FilterSet):
    ide_cUF = django_filters.CharFilter(field_name='ide__cUF', lookup_expr='icontains')
    emitente_nome = django_filters.CharFilter(field_name='emitente__xNome', lookup_expr='icontains')

    class Meta:
        model = NotaFiscal
        fields = ['ide_cUF', 'emitente_nome']


class ProdutoFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")
    cProd = django_filters.CharFilter(field_name='cProd', lookup_expr='icontains')
    xProd = django_filters.CharFilter(field_name='xProd', lookup_expr='icontains')
    cEAN = django_filters.CharFilter(field_name='cEAN', lookup_expr='icontains')

    class Meta:
        model = Produto
        fields = ['cProd', 'xProd', 'cEAN']

    def filter_by_q(self, queryset, name, value):
        if value:
            # Usando Q para aplicar OR entre as colunas
            return queryset.filter(
                Q(cProd__icontains=value) |
                Q(xProd__icontains=value) |
                Q(cEAN__icontains=value)
            )
        return queryset


class FornecedorFilter(django_filters.FilterSet):
    cnpj = django_filters.CharFilter(field_name='CNPJ', lookup_expr='icontains')
    xNome = django_filters.CharFilter(field_name='xNome', lookup_expr='icontains')

    class Meta:
        model = Emitente
        fields = ['CNPJ', 'xNome']
