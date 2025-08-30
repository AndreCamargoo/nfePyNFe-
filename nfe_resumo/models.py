from django.db import models
from empresa.models import Empresa


class ResumoNFe(models.Model):
    TIPO_NF_CHOICES = (
        (0, 'Entrada'),
        (1, 'Saída'),
    )

    SITUACAO_NFE_CHOICES = (
        (1, 'Autorizada'),
        (2, 'Cancelada'),
        (3, 'Denegada'),
    )

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='resumos_nfe')
    chave_nfe = models.CharField(max_length=44, verbose_name='Chave da NFe', unique=True)
    cnpj_emitente = models.CharField(max_length=14, verbose_name='CNPJ Emitente')
    nome_emitente = models.CharField(max_length=100, verbose_name='Nome do Emitente')
    inscricao_estadual = models.CharField(max_length=14, verbose_name='Inscrição Estadual')
    data_emissao = models.DateTimeField(verbose_name='Data de Emissão')
    tipo_nf = models.PositiveIntegerField(choices=TIPO_NF_CHOICES, verbose_name='Tipo de NF')
    valor_nf = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Valor da NF')
    digest_value = models.CharField(max_length=100, verbose_name='Valor do Digest')
    data_recebimento = models.DateTimeField(verbose_name='Data de Recebimento')
    numero_protocolo = models.CharField(max_length=15, verbose_name='Número do Protocolo')
    situacao_nfe = models.PositiveIntegerField(choices=SITUACAO_NFE_CHOICES, verbose_name='Situação da NFe')
    file_xml = models.FileField(upload_to='xml/resumos/', verbose_name='Arquivo XML')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Resumo NFe'
        verbose_name_plural = 'Resumos NFe'

    def __str__(self):
        return f'{self.chave_nfe} - {self.nome_emitente}'
