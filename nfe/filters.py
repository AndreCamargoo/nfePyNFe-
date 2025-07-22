import django_filters
from .models import NotaFiscal, Produto, Emitente


class NotaFiscalFilter(django_filters.FilterSet):
    ide_cUF = django_filters.CharFilter(field_name='ide__cUF', lookup_expr='icontains')
    emitente_nome = django_filters.CharFilter(field_name='emitente__xNome', lookup_expr='icontains')

    class Meta:
        model = NotaFiscal
        fields = ['ide_cUF', 'emitente_nome']


class ProdutoFilter(django_filters.FilterSet):
    cProd = django_filters.CharFilter(field_name='cProd', lookup_expr='icontains')
    xProd = django_filters.CharFilter(field_name='xProd', lookup_expr='icontains')

    class Meta:
        model = Produto
        fields = ['cProd', 'xProd', 'nItem']


class FornecedorFilter(django_filters.FilterSet):
    cnpj = django_filters.CharFilter(field_name='CNPJ', lookup_expr='icontains')
    xNome = django_filters.CharFilter(field_name='xNome', lookup_expr='icontains')
    
    class Meta:
        model = Emitente
        fields = ['CNPJ', 'xNome']