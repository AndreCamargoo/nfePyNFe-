from django.urls import path
from . import views


urlpatterns = [
    path('nfes/', views.NfeListCreateAPIView.as_view(), name='nfe-create-list'),
    path('nfes/<int:pk>/', views.NfeRetrieveUpdateDestroyAPIView.as_view(), name='nfe-detail-view'),
    path('nfes/cnpj/', views.NfeListAPIView.as_view(), name='nfe-detail-nfe'),
    path('nfes/cnpj/<int:documento>/', views.NfeListAPIView.as_view(), name='nfe-detail-filial-nfe'),
    path('nfes/produtos/', views.NfeProdutosListAPIView.as_view(), name="nfe-detail-produto"),
    path('nfes/produtos/<int:documento>/', views.NfeProdutosListAPIView.as_view(), name="nfe-detail-produto-filial"),
    path('nfes/forncedor/', views.NfeFornecedorListAPIView.as_view(), name='nfe-list-fornecedor'),
    path('nfes/forncedor/detalhes/<int:pk>/', views.NfeFornecedorDetailListAPIView.as_view(), name='nfe-detail-fornecedor'),
    path('nfes/forncedor/<int:documento>/', views.NfeFornecedorListAPIView.as_view(), name='nfe-detail-fornecedor-filial'),
    path('nfes/analises-faturamento/', views.NfeFaturamentoAPIView.as_view(), name='nfe-analises-faturamento'),
    path('nfes/analises-faturamento-mes/', views.NfeFaturamentoMesAPIView.as_view(), name='nfe-analises-faturamento-mes'),
    path('nfes/analises-produdos/', views.NfeProdutosAPIView.as_view(), name='nfe-analises-produtos'),
    path('nfes/gerar-danfe/<int:pk>/', views.GerarDanfeAPIView.as_view(), name='nfe-gerar-danfe'),
]
