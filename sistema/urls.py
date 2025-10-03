from django.urls import path
from . import views


urlpatterns = [
    path('sistemas/', views.SistemaListCreateAPIView.as_view(), name='sistema-create-list'),
    path('sistema/<int:pk>/', views.SistemaRetrieveUpdateDestroyAPIView.as_view(), name='sistema-detail'),

    path('sistemas/empresas/<int:empresa_id>', views.EmpresaSistemaListCreateAPIView.as_view(), name='empresa-sistema-list-create'),
    path('sistema/empresa/<int:pk>/', views.EmpresaSistemaRetrieveUpdateDestroyAPIView.as_view(), name='empresa-sistema-detail'),

    path('sistemas/rotas/', views.RotaSistemaListCreateAPIView.as_view(), name='rota-sistema-list-create'),
    path('sistema/rota/<int:pk>/', views.RotaSistemaRetrieveUpdateDestroyAPIView.as_view(), name='rota-sistema-detail'),

    path('sistemas/grupos-rotas/', views.GrupoRotaSistemaListCreateAPIView.as_view(), name='grupo-rota-sistema-list-create'),
    path('sistema/grupo-rota/<int:pk>/', views.GrupoRotaSistemaRetrieveUpdateDestroyAPIView.as_view(), name='grupo-rota-sistema-detail'),
]
