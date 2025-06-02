from rest_framework import permissions


class NfePermissionClass(permissions.BasePermission):
    """
    Permissão personalizada para ações sobre Nota Fiscal.
    Requer permissões específicas dependendo do método HTTP.
    """
    def has_permission(self, request, view):
        if request.method in ['GET', 'OPTIONS', 'HEAD']:
            # Requer as duas permissões para leitura
            return self.__has_any_perm(request.user, [
                'nfe.view_notafiscal',
                'nfe.view_ide',
                'nfe.view_emitente',
                'nfe.view_destinatario',
                'nfe.view_produto',
                'nfe.view_imposto',
                'nfe.view_total',
                'nfe.view_transporte',
                'nfe.view_cobranca',
                'nfe.view_pagamento',
            ])
        elif request.method == 'POST':
            return request.user.has_perm('nfe.add_notafiscal')
        elif request.method in ['PUT', 'PATCH']:
            return request.user.has_perm('nfe.change_notafiscal')
        elif request.method == 'DELETE':
            return request.user.has_perm('nfe.delete_notafiscal')
        return False

    def __has_all_perms(user, perms):
        """Verifica se o usuário tem todas as permissões da lista."""
        return all(user.has_perm(perm) for perm in perms)

    def __has_any_perm(user, perms):
        """Verifica se o usuário tem pelo menos uma das permissões da lista."""
        return any(user.has_perm(perm) for perm in perms)
