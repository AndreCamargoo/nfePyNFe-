from django.urls import path
from . import views


urlpatterns = [
    path('empresas/', views.EmpresaListCreateAPIView.as_view(), name='empresa-create-list'),
    path('empresa/<int:pk>/', views.EmpresaRetrieveUpdateDestroyAPIView.as_view(), name='empresa-detail-view'),

    path('categorias/', views.CategoriaEmpresaListCreateAPIView.as_view(), name='categoriaempresa-create-list'),
    path('categoria/<int:pk>/', views.CategoriaEmpresaRetrieveUpdateDestroyAPIView.as_view(), name='categoriaempresa-detail-view'),

    path('database/', views.ConexaoBancoListCreateAPIView.as_view(), name='conexaobanco-create-list'),
]
