
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied

from django.shortcuts import get_object_or_404

from empresa.models import Funcionario, Empresa
from sistema.models import EmpresaSistema


class CustomPageSizePagination(PageNumberPagination):
    page_size = 10  # valor padrão (equivale ao settings.py)
    page_size_query_param = 'pageSize'
    max_page_size = 100  # limite para evitar abuso


def get_empresas_filtradas(user, documento):
    if documento:
        minha_empresa = get_object_or_404(Empresa, usuario_id=user.id, documento=documento)
        empresas_filtradas = Empresa.objects.filter(documento=documento, matriz_filial=minha_empresa)
    else:
        minha_empresa = get_object_or_404(Empresa, pk=user.id)
        empresas_filtradas = Empresa.objects.filter(pk=minha_empresa.id)

    if not empresas_filtradas.exists():
        print('Nenhuma filial encontrada. Usando a empresa principal.')
        empresas_filtradas = Empresa.objects.filter(pk=minha_empresa.id)

    return empresas_filtradas


def verificaRestricaoAdministrativa(empresa_id, sistema_id):
    restricaoAdministrativa = EmpresaSistema.objects.filter(
        empresa=empresa_id,
        sistema=sistema_id,
        ativo=False
    ).exists()

    if restricaoAdministrativa:
        return False

    return True


def obter_matriz_funcionario(user):
    """
    Função utilitária para obter a matriz do funcionário
    Pode ser reutilizada em qualquer view
    """
    try:
        # Verifica se é funcionário ativo
        funcionario = Funcionario.objects.filter(
            user=user,
            status='1',
            role='funcionario',
            empresa__sistema_id=3
        ).select_related('empresa').first()

        if funcionario:
            empresa = funcionario.empresa
            return empresa.id
        else:
            # Usuário não é funcionário - pega primeira matriz
            matriz = Empresa.objects.filter(
                usuario=user,
                matriz_filial__isnull=True,
                status='1',
                sistema_id=3
            ).first()

            if matriz:
                print(f"Matriz encontrada - Empresa ID: {matriz.id}")
                return matriz.id
            else:
                filial = Empresa.objects.filter(
                    usuario=user,
                    status='1',
                    sistema_id=3
                ).first()

                if filial:
                    print(f"Matriz encontrada - Empresa ID: {filial.id}")
                    return filial.id

            print("Nenhuma matriz encontrada")
            return None

    except Exception as e:
        print(f"Erro ao obter matriz: {e}")
        return None
