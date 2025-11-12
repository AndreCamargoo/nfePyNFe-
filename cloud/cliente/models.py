from django.contrib.auth.models import User
from django.db import models
from cloud.segmento.models import Segmento
from empresa.models import Empresa


class StatusChoices(models.TextChoices):
    ATIVO = '1', 'Ativo'
    INATIVO = '2', 'Inativo'


class TipoArquivoChoices(models.TextChoices):
    DOCUMENTO = '1', 'Documento'
    PLANILHA = '2', 'Planilha'
    IMAGEM = '3', 'Imagem'
    PDF = '4', 'PDF'
    OUTRO = '5', 'Outro'


class Pasta(models.Model):
    nome = models.CharField(max_length=255)
    pasta_pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subpastas'
    )
    segmento = models.ForeignKey(
        Segmento,
        on_delete=models.CASCADE,
        related_name='pastas_do_segmento'
    )
    status = models.CharField(max_length=1, choices=StatusChoices.choices, default=StatusChoices.ATIVO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    deletado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cloud_pasta'
        verbose_name = 'Pasta'
        verbose_name_plural = 'Pastas'

    def __str__(self):
        return f"{self.nome} - {self.segmento.nome}"


class Cliente(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='clientes_do_usuario'
    )
    segmentos = models.ManyToManyField(
        Segmento,
        related_name="clientes_do_segmento",
    )
    pastas = models.ManyToManyField(
        Pasta,
        related_name="clientes_da_pasta",
    )
    status = models.CharField(max_length=1, choices=StatusChoices.choices, default=StatusChoices.ATIVO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    deletado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cloud_cliente'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return f"Cliente {self.id} - {self.empresa.usuario.get_full_name() or self.empresa.razao_social}"


class Arquivo(models.Model):
    nome = models.CharField(max_length=255)
    nome_original = models.CharField(max_length=255)  # Nome original do arquivo
    arquivo = models.FileField(upload_to='arquivos/%Y/%m/%d/')  # Campo para upload
    pasta = models.ForeignKey(
        Pasta,
        on_delete=models.CASCADE,
        related_name='arquivos_da_pasta'
    )
    tipo = models.CharField(max_length=1, choices=TipoArquivoChoices.choices, default=TipoArquivoChoices.OUTRO)
    extensao = models.CharField(max_length=10)
    tamanho = models.BigIntegerField(default=0)
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='arquivos_da_empresa'
    )
    criado_por = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='arquivos_criados'
    )
    status = models.CharField(max_length=1, choices=StatusChoices.choices, default=StatusChoices.ATIVO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    deletado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cloud_arquivo'
        verbose_name = 'Arquivo'
        verbose_name_plural = 'Arquivos'
        indexes = [
            models.Index(fields=['pasta', 'status']),
            models.Index(fields=['empresa', 'criado_em']),
        ]

    def __str__(self):
        return f"{self.nome} - {self.pasta.nome}"

    def save(self, *args, **kwargs):
        # Auto-preencher nome_original se não fornecido
        if not self.nome_original and self.arquivo:
            self.nome_original = self.arquivo.name
        # Auto-detectar extensão
        if self.arquivo and not self.extensao:
            self.extensao = self.arquivo.name.split('.')[-1].lower()
        # Auto-calcular tamanho
        if self.arquivo and self.tamanho == 0:
            try:
                self.tamanho = self.arquivo.size
            except:
                self.tamanho = 0
        super().save(*args, **kwargs)


class AdministradorPasta(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="empresa_pastas"
    )
    pasta = models.ForeignKey(
        Pasta,
        on_delete=models.CASCADE,
        related_name="administradores_da_pasta"
    )
    funcionario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pastas_administradas"
    )
    data_designacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cloud_clientes_administrador_pasta'
        verbose_name = 'Administrador de Pasta'
        verbose_name_plural = 'Administradores de Pastas'
        unique_together = ['pasta', 'funcionario']

    def __str__(self):
        return f"{self.funcionario.username} - {self.pasta.nome}"
