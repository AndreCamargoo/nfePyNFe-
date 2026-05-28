from django.urls import path
from . import views

urlpatterns = [
    # Segmentos (Pastas Raiz)
    path('azevedo-cloud/segmentos/', views.SegmentoListCreateAPIView.as_view(), name='segmento-list-create'),
    path('azevedo-cloud/segmentos/<int:pk>/', views.SegmentoRetrieveUpdateDestroyAPIView.as_view(), name='segmento-detail'),

    # Subpastas
    path('azevedo-cloud/subpastas/', views.SubpastaListCreateAPIView.as_view(), name='subpasta-list-create'),
    path('azevedo-cloud/subpastas/<int:pk>/', views.SubpastaRetrieveUpdateDestroyAPIView.as_view(), name='subpasta-detail'),

    # Permissão para usuarios em segmentos
    path('azevedo-cloud/permissao-usuario-segmento/', views.PermissaoUsuarioSegmentoListAPIView.as_view(), name='permissao-usuario-segmento-list'),

    # Lista empresas somente vinculadas ao azevedo cloud
    path('azevedo-cloud/lista-empresas-relacionadas/', views.ListCompanyListAPIView.as_view(), name='list-company-related'),

    # Arquivos
    path('azevedo-cloud/arquivos/', views.ArquivoListCreateAPIView.as_view(), name='arquivo-list-create'),
    path('azevedo-cloud/arquivos/<int:pk>/', views.ArquivoRetrieveUpdateDestroyAPIView.as_view(), name='arquivo-detail'),

    # Circularizações (Links Externos)
    path('azevedo-cloud/circularizacoes/', views.CircularizacaoListCreateAPIView.as_view(), name='circularizacao-list-create'),
    path('azevedo-cloud/circularizacoes/<int:pk>/', views.CircularizacaoRetrieveUpdateDestroyAPIView.as_view(), name='circularizacao-detail'),

    # Navegação e Deep Links
    path('azevedo-cloud/clientes-acesso/', views.ClientesComAcessoAPIView.as_view(), name='clientes-acesso'),
    path('azevedo-cloud/navegacao/<int:cliente_id>/', views.NavegacaoSegmentoAPIView.as_view(), name='navegacao-segmento'),
    path('azevedo-cloud/subpasta/<int:subpasta_id>/arquivos/<int:cliente_id>/', views.SubpastaArquivosAPIView.as_view(), name='subpasta-arquivos'),

    # Acesso Convidado (Link Externo)
    path('azevedo-cloud/guest/circularizacao/<uuid:uuid>/', views.GuestAcessoCircularizacaoAPIView.as_view(), name='guest-circularizacao'),
]
