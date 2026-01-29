from django.urls import path
from . import views


urlpatterns = [
    path('categorias/', views.CategoriaEmpresaListCreateAPIView.as_view(), name='categoriaempresa-create-list'),
    path('categoria/<int:pk>/', views.CategoriaEmpresaRetrieveUpdateDestroyAPIView.as_view(), name='categoriaempresa-detail-view'),

    path('empresas/', views.EmpresaListCreateAPIView.as_view(), name='empresa-create-list'),
    path('empresa/<int:pk>/', views.EmpresaRetrieveUpdateDestroyAPIView.as_view(), name='empresa-detail-view'),
    path('empresa/minha/', views.EmpresaPorUsuarioAPIView.as_view(), name='empresa-minha'),
    path('empresa/todas/', views.EmpresasGeraisAPIView.as_view(), name='empresas-gerais'),

    path('database/', views.ConexaoBancoListCreateAPIView.as_view(), name='conexaobanco-create-list'),

    path('funcionarios/', views.FuncionarioListCreateAPIView.as_view(), name='funcionario-create-list'),
    path('funcionario/<int:pk>/', views.FuncionarioRetrieveUpdateDestroyAPIView.as_view(), name='funcionario-detail-view'),
    path('funcionarios/todos/', views.FuncionarioGeraisAPIView.as_view(), name='funcionario-gerais'),
    path('funcionarios/admin/<int:pk>/', views.FuncionarioAdminDetail.as_view(), name='funcionario-admin-detail'),

    path('funcionarios/rotas/', views.FuncionarioRotasListCreateAPIView.as_view(), name='funcionario-rotas-create-list'),
    path('funcionario/rota/<int:pk>/', views.FuncionarioRotasRetrieveUpdateDestroyAPIView.as_view(), name='funcionario-rota-detail-view'),

    path('empresa/create-admin/<int:pk>/', views.EmpresaAdminDetailAPIView.as_view(), name='empresa-admin-detail'),
    path('empresa/create-admin/', views.CriarEmpresaAdminAPIView.as_view(), name='empresa-create-admin'),
]
