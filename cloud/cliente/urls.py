from django.urls import path
from . import views


urlpatterns = [
    path('cloud/pastas/', views.PastaListCreateAPIView.as_view(), name='pastas-create-list'),
    path('cloud/pasta/<int:pk>/', views.PastaRetrieveUpdateDestroyAPIView.as_view(), name='pasta-detail'),

    path('cloud/subpastas/', views.SubPastaListAPIView.as_view(), name='subPastas-list'),
    path('cloud/subpastas/<int:pk>/', views.SubPastaDirectListAPIView.as_view(), name='subPasta-detail'),

    path('cloud/arquivos/', views.ArquivoListCreateAPIView.as_view(), name='arquivo-create-list'),
    path('cloud/arquivo/<int:pk>/', views.ArquivoRetrieveUpdateDestroyAPIView.as_view(), name='arquivo-detail'),
    path('cloud/arquivos/pasta/<int:pasta_id>/', views.ArquivoListByPastaAPIView.as_view(), name='arquivo-list-by-pasta'),

    path('cloud/arquivos/drive/<str:drive>/', views.ArquivoListByDriveAPIView.as_view(), name='arquivo-list-by-drive'),
    path('cloud/estatisticas/drive/', views.EstatisticasDriveAPIView.as_view(), name='estatisticas-drive'),

    # Download arquivos
    path('cloud/download/arquivo/<int:arquivo_id>/', views.DownloadArquivoAPIView.as_view(), name='download-arquivo'),
    path('cloud/download/pasta/<int:pasta_id>/', views.DownloadPastaAPIView.as_view(), name='download-pasta'),
    path('cloud/download/multiplos/', views.DownloadMultiplosArquivosAPIView.as_view(), name='download-multiplos'),

    path('cloud/clientes/', views.ClienteListCreateAPIView.as_view(), name='cliente-create-list'),
    path('cloud/cliente/<int:pk>/', views.ClienteRetrieveUpdateDestroyAPIView.as_view(), name='cliente-detail'),

    path('cloud/permissao-pasta-clientes/', views.AdministradorPastaListCreateAPIView.as_view(), name='cliente-vincular-create-list'),
    path('cloud/permissao-pasta-cliente/<int:pk>/', views.AdministradorPastaRetrieveUpdateDestroyAPIView.as_view(), name='cliente-vincular-detail'),
    path('cloud/permissao-pasta-cliente/funcionario/<int:funcionario_id>/', views.PastaListByFuncionarioAPIView.as_view(), name='cliente-list-by-empresa'),

    path('cloud/permissao-pasta-clientes/<int:pasta_id>/', views.AdministradorPastaListAPIView.as_view(), name='cliente-permissao-list'),
    path('cloud/permissao-pasta-clientes/bulk/', views.AdministradorPastaBulkCreateAPIView.as_view(), name='cliente-vincular-bulk'),
    path('cloud/permissao-pasta-clientes/<int:pasta_id>/update/', views.AdministradorPastaBulkUpdateAPIView.as_view(), name='cliente-permissao-update'),

    path('cloud/pastas-fixadas/', views.PastaFixadaListCreateAPIView.as_view(), name='pastas-fixadas'),
    path('cloud/pastas-fixadas/<int:pk>/', views.PastaFixadaDestroyAPIView.as_view(), name='pasta-fixada-remove'),
    path('cloud/pastas-fixadas/user/', views.PastaFixadaListFilteredAPIView.as_view(), name='pastas-fixadas-filtered'),

    path('cloud/pastas-recentes/', views.PastaRecenteListAPIView.as_view(), name='pastas-recentes'),
    path('cloud/pasta/<int:pasta_id>/registrar-acesso/', views.RegistrarAcessoPastaAPIView.as_view(), name='registrar-acesso-pasta'),
    path('cloud/pasta/user/', views.PastaRecenteListFilteredAPIView.as_view(), name='pasta-recente-filtered'),

    path('cloud/dashboard-pastas/', views.DashboardPastasAPIView.as_view(), name='dashboard-pastas'),
]
