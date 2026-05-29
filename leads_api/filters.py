import re
import django_filters
from django.db.models import Q, Value
from .models import Lead, Cnes, Municipalities
from django.db.models.functions import Replace


class LeadsFilter(django_filters.FilterSet):
    # Busca geral
    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")

    # Campos de texto
    empresa = django_filters.CharFilter(field_name='empresa', lookup_expr='icontains')
    apelido = django_filters.CharFilter(field_name='apelido', lookup_expr='icontains')
    telefone = django_filters.CharFilter(method='filter_telefone')
    cnpj = django_filters.CharFilter(field_name='cnpj', lookup_expr='icontains')
    cidade = django_filters.CharFilter(field_name='cidade', lookup_expr='iexact')
    estado = django_filters.CharFilter(field_name='estado', lookup_expr='iexact')
    segmento = django_filters.CharFilter(field_name='segmento', lookup_expr='icontains')
    classificacao = django_filters.CharFilter(field_name='classificacao', lookup_expr='iexact')
    origem = django_filters.CharFilter(field_name='origem', lookup_expr='icontains')

    # Relacionamentos
    empresas_grupo = django_filters.NumberFilter(field_name='empresas_grupo__id')
    produtos_interesse = django_filters.NumberFilter(field_name='produtos_interesse__id')

    class Meta:
        model = Lead
        fields = [
            'empresa', 'apelido', 'telefone', 'cnpj',
            'cidade', 'estado', 'segmento', 'classificacao', 'origem',
            'empresas_grupo', 'produtos_interesse'
        ]

    # Normalização de telefone
    def normalize_telefone_queryset(self, queryset):
        return queryset.annotate(
            telefone_limpo=Replace(
                Replace(
                    Replace(
                        Replace(
                            Replace('telefone', Value('('), Value('')),
                            Value(')'), Value('')
                        ),
                        Value('-'), Value('')
                    ),
                    Value(' '), Value('')
                ),
                Value('+'), Value('')
            )
        )

    def clean_number(self, value):
        return re.sub(r'\D', '', value or '')

    # Filtro de telefone
    def filter_telefone(self, queryset, name, value):
        if not value:
            return queryset

        numero = self.clean_number(value)
        queryset = self.normalize_telefone_queryset(queryset)

        return queryset.filter(telefone_limpo__icontains=numero)

    # Busca geral
    def filter_by_q(self, queryset, name, value):
        if not value:
            return queryset

        numero = self.clean_number(value)
        queryset = self.normalize_telefone_queryset(queryset)

        filters = (
            Q(empresa__icontains=value) | Q(apelido__icontains=value) | Q(cnpj__icontains=value) |
            Q(cidade__icontains=value) | Q(contatos__nome__icontains=value)
        )

        # Se tiver número na busca, inclui telefone
        if numero:
            filters |= Q(telefone_limpo__icontains=numero)

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
    cpf_cnpj = django_filters.CharFilter(method='filter_cpf_cnpj')

    def filter_cpf_cnpj(self, queryset, name, value):
        """Busca por CNPJ/CPF aceitando valor com ou sem formatação.

        O banco pode armazenar '46.339.441/0001-13' enquanto o frontend envia
        '46339441000113'. Normaliza ambos os lados para garantir o match.
        """
        clean = re.sub(r'[^0-9]', '', value)
        q = Q(cpf_cnpj__icontains=value)
        if clean:
            # Formata como CNPJ (14 dígitos) para buscar no formato armazenado
            if len(clean) == 14:
                formatted = f"{clean[:2]}.{clean[2:5]}.{clean[5:8]}/{clean[8:12]}-{clean[12:14]}"
                q |= Q(cpf_cnpj__iexact=formatted)
            elif len(clean) == 11:
                # CPF: XXX.XXX.XXX-XX
                formatted = f"{clean[:3]}.{clean[3:6]}.{clean[6:9]}-{clean[9:11]}"
                q |= Q(cpf_cnpj__iexact=formatted)
            # Busca parcial com os dígitos limpos também (cobre formatos mistos)
            q |= Q(cpf_cnpj__icontains=clean)
        return queryset.filter(q)
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


class MunicipalitiesFilter(django_filters.FilterSet):
    # Busca geral
    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")

    # Filtros texto
    co_municip = django_filters.CharFilter(field_name='co_municip', lookup_expr='icontains')
    ds_nome = django_filters.CharFilter(field_name='ds_nome', lookup_expr='icontains')
    ds_nomepad = django_filters.CharFilter(field_name='ds_nomepad', lookup_expr='icontains')
    co_uf = django_filters.CharFilter(field_name='co_uf', lookup_expr='iexact')

    class Meta:
        model = Municipalities
        fields = [
            'co_municip',
            'ds_nome',
            'ds_nomepad',
            'co_uf',
        ]

    def filter_by_q(self, queryset, name, value):
        if not value:
            return queryset

        filters = (
            Q(co_municip__icontains=value) | Q(ds_nome__icontains=value) |
            Q(ds_nomepad__icontains=value) | Q(co_uf__icontains=value)
        )

        return queryset.filter(filters)
