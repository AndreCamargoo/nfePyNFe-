from django.db import models
from empresa.models import Empresa


class EventoNFe(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='eventos_nfe')
    chave_nfe = models.CharField(max_length=44, verbose_name='Chave da NFe')
    tipo_evento = models.CharField(max_length=10, verbose_name='Tipo de Evento')
    sequencia_evento = models.PositiveIntegerField(verbose_name='Sequência do Evento')
    data_hora_evento = models.DateTimeField(verbose_name='Data/Hora do Evento')
    data_hora_registro = models.DateTimeField(verbose_name='Data/Hora do Registro')
    descricao_evento = models.CharField(max_length=100, verbose_name='Descrição do Evento')
    numero_protocolo = models.CharField(max_length=15, verbose_name='Número do Protocolo')
    status = models.CharField(max_length=3, verbose_name='Status')
    motivo = models.TextField(verbose_name='Motivo')
    versao_aplicativo = models.CharField(max_length=20, verbose_name='Versão do Aplicativo')
    orgao = models.CharField(max_length=2, verbose_name='Órgão')
    ambiente = models.PositiveIntegerField(choices=((1, 'Produção'), (2, 'Homologação')), verbose_name='Ambiente')
    cnpj_destinatario = models.CharField(max_length=14, verbose_name='CNPJ Destinatário')
    file_xml = models.FileField(upload_to='xml/', verbose_name='Arquivo XML')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Evento NFe'
        verbose_name_plural = 'Eventos NFe'
        unique_together = ['chave_nfe', 'sequencia_evento', 'tipo_evento']

    def __str__(self):
        return f'{self.chave_nfe} - {self.get_tipo_evento_display()}'


class SignatureEvento(models.Model):
    evento = models.OneToOneField(EventoNFe, on_delete=models.CASCADE, related_name='signature')
    signature_value = models.TextField(verbose_name='Valor da Assinatura')
    canonicalization_method = models.CharField(max_length=100, verbose_name='Método de Canonicalização')
    signature_method = models.CharField(max_length=100, verbose_name='Método de Assinatura')
    digest_method = models.CharField(max_length=100, verbose_name='Método de Digest')
    digest_value = models.CharField(max_length=100, verbose_name='Valor do Digest')
    x509_certificate = models.TextField(verbose_name='Certificado X509')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Assinatura do Evento'
        verbose_name_plural = 'Assinaturas de Eventos'


class RetornoEvento(models.Model):
    evento = models.OneToOneField(EventoNFe, on_delete=models.CASCADE, related_name='retorno')
    tp_amb = models.PositiveIntegerField(choices=((1, 'Produção'), (2, 'Homologação')), verbose_name='Tipo Ambiente')
    ver_aplic = models.CharField(max_length=20, verbose_name='Versão Aplicativo')
    c_orgao = models.CharField(max_length=2, verbose_name='Código Órgão')
    c_stat = models.CharField(max_length=3, verbose_name='Código Status')
    x_motivo = models.TextField(verbose_name='Motivo')
    ch_nfe = models.CharField(max_length=44, verbose_name='Chave NFe')
    tp_evento = models.CharField(max_length=6, verbose_name='Tipo Evento')
    x_evento = models.CharField(max_length=100, verbose_name='Descrição Evento')
    n_seq_evento = models.PositiveIntegerField(verbose_name='Sequência Evento')
    cnpj_dest = models.CharField(max_length=14, verbose_name='CNPJ Destinatário')
    dh_reg_evento = models.DateTimeField(verbose_name='Data/Hora Registro')
    n_prot = models.CharField(max_length=15, verbose_name='Número Protocolo')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Retorno do Evento'
        verbose_name_plural = 'Retornos de Eventos'
