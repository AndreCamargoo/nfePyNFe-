from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from empresa.models import Empresa
from app.permissions import GlobalDefaultPermission
from empresa.serializer import EmpresaModelSerializer


class EmpresaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = Empresa.objects.all()
    serializer_class = EmpresaModelSerializer


class EmpresaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = Empresa.objects.all()
    serializer_class = EmpresaModelSerializer

    def patch(self, request, *args, **kwargs):
        # Torna a atualização parcial, permitindo apenas os campos enviados
        return self.update(request, *args, partial=True, **kwargs)


class FiliaisListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = Empresa.objects.all()
    serializer_class = EmpresaModelSerializer

    def get_queryset(self):
        # Filtra apenas as empresas que são filiais
        return self.queryset.filter(matriz_filial_id=self.request.user.id)
