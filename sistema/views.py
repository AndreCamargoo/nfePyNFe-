from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from app.permissions import GlobalDefaultPermission
from sistema.models import Sistema, EmpresaSistema, RotaSistema, GrupoRotaSistema
from sistema.serializer import (
    SistemaSerializer, EmpresaSistemaSerializer,
    EmpresaSistemaModelSerializer, RotaSistemaModelSerializer,
    GrupoRotaSistemaListSerializer, GrupoRotaSistemaCreateSerializer
)


class SistemaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = Sistema.objects.all()
    serializer_class = SistemaSerializer


class SistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = Sistema.objects.all()
    serializer_class = SistemaSerializer


class EmpresaSistemaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    serializer_class = EmpresaSistemaModelSerializer

    def get_queryset(self):
        empresa_id = self.kwargs['empresa_id']
        return EmpresaSistema.objects.filter(empresa_id=empresa_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['view'] = self
        return context


class EmpresaSistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = EmpresaSistema.objects.all()
    serializer_class = EmpresaSistemaSerializer


class RotaSistemaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = RotaSistema.objects.all()
    serializer_class = RotaSistemaModelSerializer


class RotaSistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = RotaSistema.objects.all()
    serializer_class = RotaSistemaModelSerializer


class GrupoRotaSistemaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GrupoRotaSistemaCreateSerializer

    def get_queryset(self):
        """Retorna apenas os grupos do usuário logado."""
        return GrupoRotaSistema.objects.filter(usuario=self.request.user)

    def get_serializer_class(self):
        """Usa serializer diferente para listagem e criação."""
        if self.request.method == 'GET':
            return GrupoRotaSistemaListSerializer
        return GrupoRotaSistemaCreateSerializer

    def get_serializer_context(self):
        """Inclui o request no contexto do serializer."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """Garante que o usuário seja definido automaticamente."""
        serializer.save()


class GrupoRotaSistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GrupoRotaSistemaListSerializer

    def get_queryset(self):
        return GrupoRotaSistema.objects.filter(usuario=self.request.user)

    def get_serializer_class(self):
        """Usa serializer diferente para diferentes métodos."""
        if self.request.method == 'GET':
            return GrupoRotaSistemaListSerializer
        return GrupoRotaSistemaCreateSerializer  # Para PUT/PATCH

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
