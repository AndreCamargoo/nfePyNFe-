from django.shortcuts import get_object_or_404
from .models import Empresa


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
