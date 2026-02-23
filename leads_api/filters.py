import django_filters
from django.db.models import Q
from .models import Lead, Cnes


class LeadsFilter(django_filters.FilterSet):
    # Campo de busca geral (q) que olha em vários campos, incluindo nome dos contatos
    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")

    # Filtros exatos ou parciais para campos de texto
    empresa = django_filters.CharFilter(field_name='empresa', lookup_expr='icontains')
    cnpj = django_filters.CharFilter(field_name='cnpj', lookup_expr='icontains')
    cidade = django_filters.CharFilter(field_name='cidade', lookup_expr='icontains')
    estado = django_filters.CharFilter(field_name='estado', lookup_expr='iexact')
    segmento = django_filters.CharFilter(field_name='segmento', lookup_expr='icontains')
    classificacao = django_filters.CharFilter(field_name='classificacao', lookup_expr='icontains')
    origem = django_filters.CharFilter(field_name='origem', lookup_expr='icontains')

    # Filtros para relacionamentos (IDs)
    # Note que usamos o nome do campo no model + __id para filtrar pela chave primária
    empresas_grupo = django_filters.NumberFilter(field_name='empresas_grupo__id')
    produtos_interesse = django_filters.NumberFilter(field_name='produtos_interesse__id')

    class Meta:
        model = Lead
        fields = ['empresa', 'cnpj', 'cidade', 'estado', 'segmento', 'classificacao', 'origem', 'empresas_grupo', 'produtos_interesse']

    def filter_by_q(self, queryset, name, value):
        if not value:
            return queryset

        # Busca por: Nome Empresa OU CNPJ OU Cidade OU Nome de algum Contato
        filters = (
            Q(empresa__icontains=value) | Q(cnpj__icontains=value) | Q(cidade__icontains=value) | Q(contatos__nome__icontains=value)
        )
        # .distinct() é importante quando filtramos por relacionamentos (contatos) para evitar duplicatas
        return queryset.filter(filters).distinct()


class CnesFilter(django_filters.FilterSet):
    # Busca geral
    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")

    # Filtros texto
    razao_social = django_filters.CharFilter(field_name='razao_social', lookup_expr='icontains')
    fantasia = django_filters.CharFilter(field_name='fantasia', lookup_expr='icontains')
    cidade = django_filters.CharFilter(field_name='cidade', lookup_expr='icontains')
    uf = django_filters.CharFilter(field_name='uf', lookup_expr='iexact')
    cnes = django_filters.CharFilter(field_name='cnes', lookup_expr='exact')
    cpf_cnpj = django_filters.CharFilter(field_name='cpf_cnpj', lookup_expr='icontains')
    tipo_unidade = django_filters.CharFilter(field_name='tipo_unidade', lookup_expr='icontains')

    # Filtros numéricos
    qtde_leitos_min = django_filters.NumberFilter(field_name='qtde_leitos', lookup_expr='gte')
    qtde_leitos_max = django_filters.NumberFilter(field_name='qtde_leitos', lookup_expr='lte')

    faturamento_min = django_filters.NumberFilter(field_name='faturamento_sus_2020', lookup_expr='gte')
    faturamento_max = django_filters.NumberFilter(field_name='faturamento_sus_2020', lookup_expr='lte')

    class Meta:
        model = Cnes
        fields = [
            'razao_social',
            'fantasia',
            'cidade',
            'uf',
            'cnes',
            'cpf_cnpj',
            'tipo_unidade',
        ]

    def filter_by_q(self, queryset, name, value):
        if not value:
            return queryset

        filters = (
            Q(razao_social__icontains=value) | Q(fantasia__icontains=value) |
            Q(cnes__icontains=value) | Q(cpf_cnpj__icontains=value) |
            Q(cidade__icontains=value)
        )

        return queryset.filter(filters)
