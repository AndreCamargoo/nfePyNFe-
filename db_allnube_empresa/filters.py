import datetime
import django_filters
from django.db.models import Q
from .models import NotaFiscalFlat, IdeFlat, EmitenteFlat, ProdutoFlat


class NotaFiscalFilterFlat(django_filters.FilterSet):
    ide_cUF = django_filters.CharFilter(method='filter_ide_cUF')
    emitente_nome = django_filters.CharFilter(method='filter_emitente_nome')
    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")
    dhEmi = django_filters.DateFromToRangeFilter(field_name='dhEmi')
    emitente_CNPJ = django_filters.CharFilter(method='filter_emitente_cnpj')
    emitente_xNome = django_filters.CharFilter(method='filter_emitente_xNome')
    chave = django_filters.CharFilter(field_name='chave', lookup_expr='icontains')

    class Meta:
        model = NotaFiscalFlat
        fields = ['ide_cUF', 'emitente_nome', 'chave', 'dhEmi', 'emitente_CNPJ', 'emitente_xNome']

    def filter_ide_cUF(self, queryset, name, value):
        """Filtra por código UF do IDE"""
        try:
            ide_ids = IdeFlat.objects.filter(cUF__icontains=value).values_list('nota_fiscal_id', flat=True)
            return queryset.filter(id__in=ide_ids)
        except Exception as e:
            print(f"Erro ao filtrar por ide_cUF: {e}")
            return queryset.none()

    def filter_emitente_nome(self, queryset, name, value):
        """Filtra por nome do emitente"""
        try:
            emitente_ids = EmitenteFlat.objects.filter(xNome__icontains=value).values_list('nota_fiscal_id', flat=True)
            return queryset.filter(id__in=emitente_ids)
        except Exception as e:
            print(f"Erro ao filtrar por emitente_nome: {e}")
            return queryset.none()

    def filter_emitente_cnpj(self, queryset, name, value):
        """Filtra por CNPJ do emitente"""
        try:
            emitente_ids = EmitenteFlat.objects.filter(CNPJ__icontains=value).values_list('nota_fiscal_id', flat=True)
            return queryset.filter(id__in=emitente_ids)
        except Exception as e:
            print(f"Erro ao filtrar por emitente_CNPJ: {e}")
            return queryset.none()

    def filter_emitente_xNome(self, queryset, name, value):
        """Filtra por razão social do emitente"""
        try:
            emitente_ids = EmitenteFlat.objects.filter(xNome__icontains=value).values_list('nota_fiscal_id', flat=True)
            return queryset.filter(id__in=emitente_ids)
        except Exception as e:
            print(f"Erro ao filtrar por emitente_xNome: {e}")
            return queryset.none()

    def filter_by_q(self, queryset, name, value):
        """Filtro de pesquisa geral"""
        filters = Q(chave__icontains=value)

        # Busca por emitente
        try:
            emitente_ids = EmitenteFlat.objects.filter(
                Q(CNPJ__icontains=value) | Q(xNome__icontains=value)
            ).values_list('nota_fiscal_id', flat=True)
            filters |= Q(id__in=emitente_ids)
        except Exception as e:
            print(f"Erro na busca por emitente: {e}")

        # Tenta interpretar como data
        possible_formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
        for fmt in possible_formats:
            try:
                date_value = datetime.datetime.strptime(value, fmt).date()
                filters |= Q(dhEmi__date=date_value)
                break
            except ValueError:
                continue

        return queryset.filter(filters)


class ProdutoFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_by_q', label="Pesquisar")
    xProd = django_filters.CharFilter(field_name='xProd', lookup_expr='icontains')
    cProd = django_filters.CharFilter(field_name='cProd', lookup_expr='icontains')
    cEAN = django_filters.CharFilter(field_name='cEAN', lookup_expr='icontains')
    emitente_CNPJ = django_filters.CharFilter(method='filter_emitente_cnpj')
    emitente_xNome = django_filters.CharFilter(method='filter_emitente_nome')
    chave = django_filters.CharFilter(method='filter_chave')
    dhEmi = django_filters.DateFromToRangeFilter(method='filter_dhEmi')

    class Meta:
        model = ProdutoFlat
        fields = ['cProd', 'xProd', 'cEAN', 'emitente_CNPJ', 'emitente_xNome', 'chave', 'dhEmi']

    def filter_by_q(self, queryset, name, value):
        filters = Q(xProd__icontains=value) | Q(cProd__icontains=value) | Q(cEAN__icontains=value)

        # Buscar por chave da nota
        nota_ids = NotaFiscalFlat.objects.filter(chave__icontains=value).values_list('id', flat=True)
        filters |= Q(nota_fiscal_id__in=nota_ids)

        # Buscar por CNPJ ou nome do emitente
        emitente_ids = EmitenteFlat.objects.filter(
            Q(CNPJ__icontains=value) | Q(xNome__icontains=value)
        ).values_list('nota_fiscal_id', flat=True)
        filters |= Q(nota_fiscal_id__in=emitente_ids)

        # Tentar interpretar como data de emissão
        possible_formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
        for fmt in possible_formats:
            try:
                date_value = datetime.datetime.strptime(value, fmt).date()
                nota_ids_date = NotaFiscalFlat.objects.filter(dhEmi__date=date_value).values_list('id', flat=True)
                filters |= Q(nota_fiscal_id__in=nota_ids_date)
                break
            except ValueError:
                continue

        return queryset.filter(filters)

    def filter_emitente_cnpj(self, queryset, name, value):
        emitente_ids = EmitenteFlat.objects.filter(CNPJ__icontains=value).values_list('nota_fiscal_id', flat=True)
        return queryset.filter(nota_fiscal_id__in=emitente_ids)

    def filter_emitente_nome(self, queryset, name, value):
        emitente_ids = EmitenteFlat.objects.filter(xNome__icontains=value).values_list('nota_fiscal_id', flat=True)
        return queryset.filter(nota_fiscal_id__in=emitente_ids)

    def filter_chave(self, queryset, name, value):
        nota_ids = NotaFiscalFlat.objects.filter(chave__icontains=value).values_list('id', flat=True)
        return queryset.filter(nota_fiscal_id__in=nota_ids)

    def filter_dhEmi(self, queryset, name, value):
        # value é um dict com 'start' e 'stop'
        nota_qs = NotaFiscalFlat.objects.all()
        if value.start:
            nota_qs = nota_qs.filter(dhEmi__gte=value.start)
        if value.stop:
            nota_qs = nota_qs.filter(dhEmi__lte=value.stop)
        nota_ids = nota_qs.values_list('id', flat=True)
        return queryset.filter(nota_fiscal_id__in=nota_ids)
