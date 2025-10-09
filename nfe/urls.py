from django.urls import path
from . import views


urlpatterns = [
    # Todas as notas matriz e filial
    path('nfes/', views.NfeListCreateAPIView.as_view(), name='nfe-create-list'),

    # Importar notas ficais através de um arquivo .zip
    path('nfes/processar-lote/', views.ProcessarLoteNFeAPIView.as_view(), name='nfe-processar-lote'),
    # Gerar danfe
    path('nfes/gerar-danfe/<int:pk>/', views.GerarDanfeAPIView.as_view(), name='nfe-gerar-danfe'),

    # Todas minhas notas matriz
    path('nfes/matriz/', views.NfeListMatrizAPIView.as_view(), name='nfe-matriz-list'),
    # Todas as notas da filial através do CNPJ
    path('nfes/filial/<int:documento>/', views.NfeListFilialAPIView.as_view(), name='nfe-filial-list'),
    # Detalhar nota fiscal
    path('nfes/<int:pk>/', views.NfeRetrieveUpdateDestroyAPIView.as_view(), name='nfe-detail-view'),

    # Todos os produtos matriz e filial
    path('nfes/produtos/', views.NfeTodosProdutosListAPIView.as_view(), name='nfe-produtos-list'),
    # Todos os produtos da matriz
    path('nfes/produtos/matriz/', views.NfeProdutosMatrizListAPIView.as_view(), name="nfe-produtos-matriz-list"),
    # Todos os produtos da filial através do CNPJ
    path('nfes/produtos/filial/<int:documento>/', views.NfeProdutosFilialListAPIView.as_view(), name="nfe-produtos-filial-list"),
    # Detalhar produto
    path('nfe/produto/<int:pk>/', views.NfeProdutoRetrieveAPIView.as_view(), name='nfe-produto-detail-view'),

    # Todos os forncedores matriz e filial
    path('nfes/forncedor/', views.NfeTodosFornecedorListAPIView.as_view(), name='nfe-fornecedor-list'),
    # Todos os forncedores da matriz
    path('nfes/forncedor/matriz/', views.NfeFornecedorMatrizListAPIView.as_view(), name='nfe-fornecedor-matriz-list'),
    # Todos os fornecedores da filial
    path('nfes/forncedor/filial/<int:documento>/', views.NfeFornecedorFilialListAPIView.as_view(), name='nfe-detail-fornecedor-filial'),
    # Detalhar filial
    path('nfes/forncedor/<int:pk>/', views.NfeFornecedorRetrieveAPIView.as_view(), name='nfe-fornecedor-detail-view'),

    ###################################################
    ### Compoem display especificos da home allnube ###
    ###################################################
    path('nfes/analises-faturamento/', views.NfeFaturamentoAPIView.as_view(), name='nfe-analises-faturamento'),
    path('nfes/analises-faturamento-mes/', views.NfeFaturamentoMesAPIView.as_view(), name='nfe-analises-faturamento-mes'),
    path('nfes/analises-produdos/', views.NfeProdutosAPIView.as_view(), name='nfe-analises-produtos'),
]
