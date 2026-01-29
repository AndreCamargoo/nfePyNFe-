import datetime
import django_filters
from django.db.models import Q
from .models import NotaFiscal, Produto, Emitente


class NotaFiscalFilter(django_filters.FilterSet):
    ide_cUF = django_filters.CharFilter(field_name='ide__cUF', lookup_expr='icontains')
    emitente_nome = django_filters.CharFilter(field_name='emitente__xNome', lookup_expr='icontains')

    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")
    dhEmi = django_filters.DateFromToRangeFilter(field_name='dhEmi')
    emitente_CNPJ = django_filters.CharFilter(field_name='emitente__CNPJ', lookup_expr='icontains')
    emitente_xNome = django_filters.CharFilter(field_name='emitente__xNome', lookup_expr='icontains')
    chave = django_filters.CharFilter(field_name='chave', lookup_expr='icontains')

    class Meta:
        model = NotaFiscal
        fields = ['ide_cUF', 'emitente_nome', 'chave', 'dhEmi', 'emitente_CNPJ', 'emitente_xNome']

    def filter_by_q(self, queryset, name, value):
        filters = (
            Q(emitente__CNPJ__icontains=value) | Q(emitente__xNome__icontains=value) | Q(chave__icontains=value)
        )

        # Tenta interpretar como data (vários formatos)
        possible_formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
        for fmt in possible_formats:
            try:
                date_value = datetime.datetime.strptime(value, fmt).date()
                filters |= Q(dhEmi__date=date_value)
                break  # para no primeiro formato válido
            except ValueError:
                continue  # tenta próximo formato

        return queryset.filter(filters)


class ProdutoFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")
    xProd = django_filters.CharFilter(field_name='xProd', lookup_expr='icontains')
    cProd = django_filters.CharFilter(field_name='cProd', lookup_expr='icontains')
    cEAN = django_filters.CharFilter(field_name='cEAN', lookup_expr='icontains')

    class Meta:
        model = Produto
        fields = ['cProd', 'xProd', 'cEAN']

    def filter_by_q(self, queryset, name, value):
        filters = (
            Q(xProd__icontains=value) |
            Q(cProd__icontains=value) |
            Q(cEAN__icontains=value)
        )
        return queryset.filter(filters)


class FornecedorFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method='filter_by_q',
        label="Pesquisar",
        help_text="Pesquisa em CNPJ, razão social ou telefone"
    )
    cnpj = django_filters.CharFilter(
        field_name='CNPJ',
        lookup_expr='icontains',
        help_text="Filtrar por CNPJ (contém)"
    )
    xNome = django_filters.CharFilter(
        field_name='xNome',
        lookup_expr='icontains',
        help_text="Filtrar por razão social (contém)"
    )
    fone = django_filters.CharFilter(
        field_name='fone',
        lookup_expr='icontains',
        help_text="Filtrar por telefone (contém)"
    )

    class Meta:
        model = Emitente
        fields = ['CNPJ', 'xNome', 'fone']

    def filter_by_q(self, queryset, name, value):
        if value:
            # Usando Q para aplicar OR entre as colunas
            return queryset.filter(
                Q(CNPJ__icontains=value) |
                Q(xNome__icontains=value) |
                Q(fone__icontains=value)
            )
        return queryset
