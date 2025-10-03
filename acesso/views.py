from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from app.permissions import OfficialRestrictedPermission
from acesso.models import UsuarioEmpresa, UsuarioSistema, UsuarioPermissaoRota
from acesso.serializer import UsuarioEmpresaModelSerializer, UsuarioSistemaModelModelSerializer, UsuarioPermissaoRotaModelModelSerializer


class UsuarioEmpresaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, OfficialRestrictedPermission]
    queryset = UsuarioEmpresa.objects.all()
    serializer_class = UsuarioEmpresaModelSerializer

    def get_queryset(self):
        """Filtra funcionários pelas empresas do usuário"""
        empresas_do_usuario = self.request.user.empresas.all()
        empresa_ids = empresas_do_usuario.values_list('id', flat=True)
        return UsuarioEmpresa.objects.filter(empresa_id__in=empresa_ids)

    def get_serializer_context(self):
        """Passa o request para o serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UsuarioEmpresaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, OfficialRestrictedPermission]
    queryset = UsuarioEmpresa.objects.all()
    serializer_class = UsuarioEmpresaModelSerializer

    def get_queryset(self):
        """Filtra funcionários pelas empresas do usuário"""
        empresas_do_usuario = self.request.user.empresas.all()
        empresa_ids = empresas_do_usuario.values_list('id', flat=True)
        return UsuarioEmpresa.objects.filter(empresa_id__in=empresa_ids)

    def get_serializer_context(self):
        """Passa o request para o serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UsuarioSistemaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, OfficialRestrictedPermission]
    queryset = UsuarioSistema.objects.all()
    serializer_class = UsuarioSistemaModelModelSerializer

    def get_queryset(self):
        """Filtra UsuarioSistema pelos funcionários das empresas do usuário"""
        empresas_do_usuario = self.request.user.empresas.all()
        empresa_ids = empresas_do_usuario.values_list('id', flat=True)

        funcionarios_do_usuario = UsuarioEmpresa.objects.filter(empresa_id__in=empresa_ids)
        funcionario_ids = funcionarios_do_usuario.values_list('id', flat=True)

        return UsuarioSistema.objects.filter(usuario_empresa_id__in=funcionario_ids)

    def get_serializer_context(self):
        """Passa o request para o serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UsuarioSistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, OfficialRestrictedPermission]
    queryset = UsuarioSistema.objects.all()
    serializer_class = UsuarioSistemaModelModelSerializer

    def get_queryset(self):
        """Filtra UsuarioSistema pelos funcionários das empresas do usuário"""
        empresas_do_usuario = self.request.user.empresas.all()
        empresa_ids = empresas_do_usuario.values_list('id', flat=True)

        funcionarios_do_usuario = UsuarioEmpresa.objects.filter(empresa_id__in=empresa_ids)
        funcionario_ids = funcionarios_do_usuario.values_list('id', flat=True)

        return UsuarioSistema.objects.filter(usuario_empresa_id__in=funcionario_ids)

    def get_serializer_context(self):
        """Passa o request para o serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UsuarioPermissaoRotaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, OfficialRestrictedPermission]
    queryset = UsuarioPermissaoRota.objects.all()
    serializer_class = UsuarioPermissaoRotaModelModelSerializer

    def get_queryset(self):
        """Filtra UsuarioPermissaoRota pelos funcionários das empresas do usuário"""
        empresas_do_usuario = self.request.user.empresas.all()
        empresa_ids = empresas_do_usuario.values_list('id', flat=True)

        funcionarios_do_usuario = UsuarioEmpresa.objects.filter(empresa_id__in=empresa_ids)
        funcionario_ids = funcionarios_do_usuario.values_list('id', flat=True)

        usuarios_sistema = UsuarioSistema.objects.filter(usuario_empresa_id__in=funcionario_ids)
        usuario_sistema_ids = usuarios_sistema.values_list('id', flat=True)

        return UsuarioPermissaoRota.objects.filter(usuario_sistema_id__in=usuario_sistema_ids)

    def get_serializer_context(self):
        """Passa o request para o serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UsuarioPermissaoRotaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, OfficialRestrictedPermission]
    queryset = UsuarioPermissaoRota.objects.all()
    serializer_class = UsuarioPermissaoRotaModelModelSerializer

    def get_queryset(self):
        """Filtra UsuarioPermissaoRota pelos funcionários das empresas do usuário"""
        empresas_do_usuario = self.request.user.empresas.all()
        empresa_ids = empresas_do_usuario.values_list('id', flat=True)

        funcionarios_do_usuario = UsuarioEmpresa.objects.filter(empresa_id__in=empresa_ids)
        funcionario_ids = funcionarios_do_usuario.values_list('id', flat=True)

        usuarios_sistema = UsuarioSistema.objects.filter(usuario_empresa_id__in=funcionario_ids)
        usuario_sistema_ids = usuarios_sistema.values_list('id', flat=True)

        return UsuarioPermissaoRota.objects.filter(usuario_sistema_id__in=usuario_sistema_ids)

    def get_serializer_context(self):
        """Passa o request para o serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
