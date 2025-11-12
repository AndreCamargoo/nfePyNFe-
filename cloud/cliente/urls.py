from django.urls import path
from . import views


urlpatterns = [
    path('cloud/pastas/', views.PastaListCreateAPIView.as_view(), name='pastas-create-list'),
    path('cloud/pasta/<int:pk>/', views.PastaRetrieveUpdateDestroyAPIView.as_view(), name='pasta-detail'),

    path('cloud/arquivos/', views.ArquivoListCreateAPIView.as_view(), name='arquivo-create-list'),
    path('cloud/arquivo/<int:pk>/', views.ArquivoRetrieveUpdateDestroyAPIView.as_view(), name='arquivo-detail'),

    path('cloud/clientes/', views.ClienteListCreateAPIView.as_view(), name='cliente-create-list'),
    path('cloud/cliente/<int:pk>/', views.ClienteRetrieveUpdateDestroyAPIView.as_view(), name='cliente-detail'),

    path('cloud/permissao-pasta-clientes/', views.AdministradorPastaListCreateAPIView.as_view(), name='cliente-vincular-create-list'),
    path('cloud/permissao-pasta-cliente/<int:pk>/', views.AdministradorPastaRetrieveUpdateDestroyAPIView.as_view(), name='cliente-vincular-detail'),
]
