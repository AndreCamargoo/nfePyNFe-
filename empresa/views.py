from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from empresa.models import Empresa
from app.permissions import GlobalDefaultPermission
from empresa.serializer import EmpresaModelSerializer
from rest_framework.exceptions import NotFound


class EmpresaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = EmpresaModelSerializer

    def get_queryset(self):
        return Empresa.objects.filter(usuario=self.request.user)


class EmpresaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = EmpresaModelSerializer

    def get_queryset(self):
        # Garante que o usuário só possa acessar suas próprias empresas
        return Empresa.objects.filter(usuario=self.request.user)

    def patch(self, request, *args, **kwargs):
        # Torna a atualização parcial (somente os campos enviados)
        return self.partial_update(request, *args, **kwargs)


class EmpresaPorUsuarioAPIView(generics.RetrieveAPIView):
    serializer_class = EmpresaModelSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        usuario_id = self.kwargs.get('usuario_id')
        empresa = Empresa.objects.filter(usuario__id=usuario_id).order_by('-id').first()
        if not empresa:
            raise NotFound("Empresa não encontrada para este usuário.")
        return empresa


class FiliaisListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = EmpresaModelSerializer

    def get_queryset(self):
        # Filtra apenas as empresas que são filiais da empresa do usuário
        return Empresa.objects.filter(matriz_filial_id=self.request.user.id)
