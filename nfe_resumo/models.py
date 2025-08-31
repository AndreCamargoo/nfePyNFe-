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

    TIPO_DOCUMENTO_CHOICES = (
        ('resNFe', 'Resumo NFe'),
        ('resEvento', 'Resumo Evento'),
    )

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='resumos_nfe')
    chave_nfe = models.CharField(max_length=44, verbose_name='Chave da NFe')
    tipo_documento = models.CharField(max_length=10, choices=TIPO_DOCUMENTO_CHOICES, verbose_name='Tipo de Documento')
    cnpj_emitente = models.CharField(max_length=14, verbose_name='CNPJ', blank=True, null=True)
    nome_emitente = models.CharField(max_length=100, verbose_name='Nome', blank=True, null=True)
    inscricao_estadual = models.CharField(max_length=14, verbose_name='Inscrição Estadual', blank=True, null=True)
    data_emissao = models.DateTimeField(verbose_name='Data de Emissão', blank=True, null=True)
    tipo_nf = models.PositiveIntegerField(choices=TIPO_NF_CHOICES, verbose_name='Tipo de NF', blank=True, null=True)
    valor_nf = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Valor da NF', blank=True, null=True)
    digest_value = models.CharField(max_length=100, verbose_name='Valor do Digest', blank=True, null=True)
    data_recebimento = models.DateTimeField(verbose_name='Data de Recebimento')
    numero_protocolo = models.CharField(max_length=20, verbose_name='Número do Protocolo')
    situacao_nfe = models.PositiveIntegerField(choices=SITUACAO_NFE_CHOICES, verbose_name='Situação da NFe', blank=True, null=True)

    # Campos específicos para resEvento
    tipo_evento = models.CharField(max_length=10, verbose_name='Tipo de Evento', blank=True, null=True)
    sequencia_evento = models.PositiveIntegerField(verbose_name='Sequência do Evento', blank=True, null=True)
    descricao_evento = models.CharField(max_length=100, verbose_name='Descrição do Evento', blank=True, null=True)
    orgao = models.CharField(max_length=2, verbose_name='Órgão', blank=True, null=True)

    file_xml = models.FileField(upload_to='xml/resumos/', verbose_name='Arquivo XML')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Resumo NFe'
        verbose_name_plural = 'Resumos NFe'
        unique_together = ['chave_nfe', 'tipo_documento']

    def __str__(self):
        return f'{self.chave_nfe} - {self.get_tipo_documento_display()}'
