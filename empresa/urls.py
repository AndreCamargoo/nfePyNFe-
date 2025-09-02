from django.urls import path
from . import views


urlpatterns = [
    path('empresas/', views.EmpresaListCreateAPIView.as_view(), name='empresa-create-list'),
    path('empresas/<int:pk>/', views.EmpresaRetrieveUpdateDestroyAPIView.as_view(), name='empresa-detail-view'),
    path('empresas/<int:usuario_id>/usuario/', views.EmpresaPorUsuarioAPIView.as_view(), name='empresas-por-usuario'),
    path('empresas/filiais/', views.FiliaisListCreateAPIView.as_view(), name='empresa-detail-view')
]
