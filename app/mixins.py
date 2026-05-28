# app/mixins.py

from rest_framework.exceptions import PermissionDenied

from empresa.models import Empresa, Funcionario


class SystemAccessMixin:
    """
    Mixin para validar acesso ao sistema antes de qualquer ação.
    """
    system_id = None
    system_name = None

    def dispatch(self, request, *args, **kwargs):
        # Verificar acesso ao sistema
        if not self.check_system_access(request):
            raise PermissionDenied(
                detail=f"Seu usuário não tem acesso ao sistema '{self.system_name or 'requerido'}'."
            )

        return super().dispatch(request, *args, **kwargs)

    def check_system_access(self, request):
        # Superusuário sempre tem acesso
        if request.user.is_superuser:
            return True

        system_id = self.system_id or getattr(request, 'sistema_id', None)

        if not system_id:
            return True

        # Verificar como dono
        if Empresa.objects.filter(
            usuario=request.user,
            status='1',
            sistema_id=system_id
        ).exists():
            return True

        # Verificar como funcionário
        if Funcionario.objects.filter(
            user=request.user,
            status='1',
            empresa__status='1',
            empresa__sistema_id=system_id
        ).exists():
            return True

        return False


class EmpresaScopeMixin:
    """
    Mixin para garantir que as operações sejam escopo da empresa do usuário.
    """

    def get_empresa_id(self):
        """Obtém o ID da empresa do usuário atual"""
        request = self.request

        # Superusuário pode especificar empresa_id
        if request.user.is_superuser:
            empresa_id = request.query_params.get('empresa_id') or request.data.get('empresa_id')
            if empresa_id:
                return int(empresa_id)

        # Buscar empresa do usuário
        # 1. Como dono
        empresa = Empresa.objects.filter(
            usuario=request.user,
            status='1'
        ).first()

        if empresa:
            return empresa.id

        # 2. Como funcionário
        funcionario = Funcionario.objects.filter(
            user=request.user,
            status='1',
            empresa__status='1'
        ).select_related('empresa').first()

        if funcionario:
            return funcionario.empresa.id

        return None

    def get_queryset(self):
        """Filtra queryset baseado na empresa do usuário"""
        queryset = super().get_queryset()
        empresa_id = self.get_empresa_id()

        if empresa_id and hasattr(queryset.model, 'empresa_id'):
            return queryset.filter(empresa_id=empresa_id)

        return queryset
