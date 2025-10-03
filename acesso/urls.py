from django.urls import path
from . import views


urlpatterns = [
    path('acessos/', views.UsuarioEmpresaListCreateAPIView.as_view(), name='usuario-empresa-list-create'),
    path('acesso/<int:pk>/', views.UsuarioEmpresaRetrieveUpdateDestroyAPIView.as_view(), name='usuario-empresa-detail'),

    path('acessos/sistemas/', views.UsuarioSistemaListCreateAPIView.as_view(), name='usuario-sistema-list-create'),
    path('acessos/sistema/<int:pk>/', views.UsuarioSistemaRetrieveUpdateDestroyAPIView.as_view(), name='usuario-sistema-detail'),

    path('acessos/rotas/', views.UsuarioPermissaoRotaListCreateAPIView.as_view(), name='usuario-permissao-rota-list-create'),
    path('acessos/rota/<int:pk>/', views.UsuarioPermissaoRotaRetrieveUpdateDestroyAPIView.as_view(), name='usuario-permissao-rota-detail'),
]
