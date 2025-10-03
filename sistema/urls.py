from django.urls import path
from . import views


urlpatterns = [
    path('sistemas/', views.SistemaListCreateAPIView.as_view(), name='sistema-create-list'),
    path('sistemas/<int:pk>/', views.SistemaRetrieveUpdateDestroyAPIView.as_view(), name='sistema-detail'),

    path('sistemas/<int:empresa_id>/empresa/', views.EmpresaSistemaListCreateAPIView.as_view(), name='empresa-sistema-list-create'),
    path('empresa-sistema/<int:pk>/', views.EmpresaSistemaRetrieveUpdateDestroyAPIView.as_view(), name='empresa-sistema-detail'),

    path('sistemas/rotas/', views.RotaSistemaListCreateAPIView.as_view(), name='rota-sistema-list-create'),
    path('sistemas/rota/<int:pk>/', views.RotaSistemaRetrieveUpdateDestroyAPIView.as_view(), name='rota-sistema-detail'),

    path('sistemas/grupos-rotas/', views.GrupoRotaSistemaListCreateAPIView.as_view(), name='grupo-rota-sistema-list-create'),
    path('sistemas/grupo-rota/<int:pk>/', views.GrupoRotaSistemaRetrieveUpdateDestroyAPIView.as_view(), name='grupo-rota-sistema-detail'),
]
