import os
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Q
from django.core.cache import cache

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from cloud.segmento.models import Segmento
from empresa.models import Empresa

from app.utils.storage_backends import conditional_storage
from app.utils.managersSoftDelete import SoftDeleteManager


class StatusChoices(models.TextChoices):
    ATIVO = '1', 'Ativo'
    INATIVO = '2', 'Inativo'


class TipoArquivoChoices(models.TextChoices):
    DOCUMENTO = '1', 'Documento'
    PLANILHA = '2', 'Planilha'
    IMAGEM = '3', 'Imagem'
    PDF = '4', 'PDF'
    OUTRO = '5', 'Outro'


class TipoDrive(models.TextChoices):
    LOCAL = '1', 'Local'
    S3 = '2', 'Amazon S3'


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
    deletado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='pasta_deletados'
    )

    objects = SoftDeleteManager()  # retorna apenas não deletados
    all_objects = models.Manager()  # acesso completo (deletados + não deletados)

    class Meta:
        db_table = 'cloud_pasta'
        verbose_name = 'Pasta'
        verbose_name_plural = 'Pastas'

    def __str__(self):
        return f"{self.nome} - {self.segmento.nome}"

    def delete(self, user=None, *args, **kwargs):
        self.status = StatusChoices.INATIVO
        self.deletado_em = timezone.now()

        if user:
            self.deletado_por = user

        self.save(update_fields=["status", "deletado_em", "deletado_por"])

        # Invalida cache da pasta pai
        if self.pasta_pai:
            self.pasta_pai.invalidate_size_cache()

    def get_individual_size(self):
        """
        Calcula o tamanho SOMENTE dos arquivos diretamente nesta pasta
        (NÃO inclui subpastas)
        """
        from django.db.models import Sum
        result = self.arquivos_da_pasta.filter(status='1').aggregate(
            total=Sum('tamanho')
        )
        return result['total'] or 0

    def get_immediate_files_count(self):
        """
        Calcula APENAS os arquivos diretamente na pasta (não inclui subpastas)
        """
        return self.arquivos_da_pasta.filter(status='1').count()

    def get_total_size(self):
        """
        Calcula o tamanho total de todos os arquivos na pasta E subpastas
        (Recursivo - inclui subpastas)
        """
        from django.db.models import Sum

        # Primeiro, pega o tamanho dos arquivos diretos nesta pasta
        size_direto = self.arquivos_da_pasta.filter(status='1').aggregate(
            total=Sum('tamanho')
        )['total'] or 0

        # Calcula recursivamente para subpastas
        size_subpastas = 0
        for subpasta in self.subpastas.filter(status='1'):
            size_subpastas += subpasta.get_total_size()

        return size_direto + size_subpastas

    def get_total_files_count(self):
        """
        Calcula o total de arquivos na pasta E subpastas
        (Recursivo - inclui subpastas)
        """
        # Conta arquivos diretos
        count_direto = self.arquivos_da_pasta.filter(status='1').count()

        # Conta recursivamente para subpastas
        count_subpastas = 0
        for subpasta in self.subpastas.filter(status='1'):
            count_subpastas += subpasta.get_total_files_count()

        return count_direto + count_subpastas

    def invalidate_size_cache(self):
        """Invalida o cache de tamanho"""
        cache.delete(f'pasta_{self.id}_individual_size')
        cache.delete(f'pasta_{self.id}_files_count')

        # Invalida também as pastas pai
        if self.pasta_pai:
            self.pasta_pai.invalidate_size_cache()


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
    status = models.CharField(max_length=1, choices=StatusChoices.choices, default=StatusChoices.ATIVO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    deletado_em = models.DateTimeField(null=True, blank=True)
    deletado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='cliente_deletados'
    )

    objects = SoftDeleteManager()  # retorna apenas não deletados
    all_objects = models.Manager()  # acesso completo (deletados + não deletados)

    class Meta:
        db_table = 'cloud_cliente'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return f"Cliente {self.id} - {self.empresa.usuario.get_full_name() or self.empresa.razao_social}"

    def delete(self, user=None, *args, **kwargs):
        self.deletado_em = timezone.now()
        if user:
            self.deletado_por = user
        self.save(update_fields=["deletado_em", "deletado_por"])


class Arquivo(models.Model):
    nome = models.CharField(max_length=255)
    nome_original = models.CharField(max_length=255)
    arquivo = models.FileField(
        upload_to='arquivos/%Y/%m/%d/',
        storage=conditional_storage
    )
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
    drive = models.CharField(max_length=1, choices=TipoDrive.choices, default=TipoDrive.LOCAL)
    deletado_em = models.DateTimeField(null=True, blank=True)
    deletado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='arquivos_deletados'
    )

    objects = SoftDeleteManager()  # retorna apenas não deletados
    all_objects = models.Manager()  # acesso completo (deletados + não deletados)

    class Meta:
        db_table = 'cloud_arquivo'
        verbose_name = 'Arquivo'
        verbose_name_plural = 'Arquivos'
        indexes = [
            models.Index(fields=['pasta', 'status']),
            models.Index(fields=['empresa', 'criado_em']),
            models.Index(fields=['drive']),
        ]

    def __str__(self):
        return f"{self.nome} - {self.pasta.nome}"

    def save(self, *args, **kwargs):
        """
        Sobrescreve o save para configurar campos automaticamente
        e evitar loop infinito
        """
        is_new = self.pk is None

        # Configura campos antes do primeiro save
        if not self.nome_original and self.arquivo:
            self.nome_original = self.arquivo.name

        if self.arquivo and not self.extensao:
            self.extensao = self._get_extensao(self.arquivo.name)

        if self.arquivo and self.tamanho == 0:
            try:
                self.tamanho = self.arquivo.size
            except:
                self.tamanho = 0

        # Determina drive baseado na configuração atual ANTES de salvar
        if not self.drive:
            if getattr(settings, 'AWS_USE_S3_UPLOAD', False):
                self.drive = TipoDrive.S3
            else:
                self.drive = TipoDrive.LOCAL

        # Salva o objeto (primeira vez)
        super().save(*args, **kwargs)

        # Não atualiza o drive aqui! Isso será feito pelo storage
        # após o arquivo ser realmente salvo no storage backend

        # Invalida o cache da pasta após salvar arquivo
        if self.pasta:
            self.pasta.invalidate_size_cache()

    def update_drive_from_storage(self):
        """
        Método para atualizar o drive baseado no storage usado
        Deve ser chamado APÓS o arquivo ser salvo no storage
        """

        # Obtém o último drive usado pelo storage
        last_drive = conditional_storage.get_last_drive_used()
        if last_drive and last_drive != self.drive:
            self.drive = last_drive
            # Atualiza APENAS o campo drive usando update para evitar loop
            Arquivo.objects.filter(pk=self.pk).update(drive=last_drive)
            return True
        return False

    def delete(self, user=None, *args, **kwargs):
        # Soft delete — NÃO remover do banco
        self.status = StatusChoices.INATIVO
        self.deletado_em = timezone.now()

        if user:
            self.deletado_por = user

        # Salva somente os campos do soft delete
        self.save(update_fields=["status", "deletado_em", "deletado_por"])

        # Invalida cache da pasta
        if self.pasta:
            self.pasta.invalidate_size_cache()

    def _get_extensao(self, filename):
        """Extrai a extensão do arquivo"""
        _, ext = os.path.splitext(filename)
        return ext.lower().replace('.', '') if ext else ''

    @property
    def url(self):
        """Retorna a URL do arquivo"""
        if self.arquivo:
            return self.arquivo.url
        return None

    @property
    def drive_info(self):
        """Informações completas sobre o drive"""
        return {
            'code': self.drive,
            'display': self.get_drive_display(),
            'is_s3': self.drive == TipoDrive.S3,
            'is_local': self.drive == TipoDrive.LOCAL,
            'storage_name': 'Amazon S3' if self.drive == TipoDrive.S3 else 'Local Storage'
        }


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
        unique_together = ['pasta', 'funcionario', 'empresa']

    def __str__(self):
        return f"{self.funcionario.username} - {self.pasta.nome}"


class PastaFixada(models.Model):
    """
    Tabela para pastas fixadas pelo usuário (máximo 10 por usuário)
    Não precisa ser autoincrement, usaremos ordem manual
    """
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pastas_fixadas"
    )
    pasta = models.ForeignKey(
        Pasta,
        on_delete=models.CASCADE,
        related_name="fixada_por_usuarios"
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="pastas_fixadas"
    )
    ordem = models.PositiveSmallIntegerField(default=0)  # Para ordenação
    fixado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cloud_pasta_fixada'
        verbose_name = 'Pasta Fixada'
        verbose_name_plural = 'Pastas Fixadas'
        unique_together = ['usuario', 'pasta']  # Um usuário não pode fixar a mesma pasta duas vezes
        ordering = ['ordem', '-fixado_em']

    def __str__(self):
        return f"{self.usuario.username} - {self.pasta.nome}"

    def save(self, *args, **kwargs):
        # Se é uma nova pasta fixada
        if not self.pk:
            # Verifica se já tem 10 pastas fixadas
            pastas_count = PastaFixada.objects.filter(usuario=self.usuario).count()
            if pastas_count >= 10:
                # Remove a mais antiga (menor ordem ou mais antiga)
                mais_antiga = PastaFixada.objects.filter(
                    usuario=self.usuario
                ).order_by('ordem', 'fixado_em').first()
                if mais_antiga:
                    mais_antiga.delete()

        # Define a ordem como a maior ordem atual + 1
        if not self.ordem:
            max_ordem = PastaFixada.objects.filter(usuario=self.usuario).aggregate(
                models.Max('ordem')
            )['ordem__max'] or 0
            self.ordem = max_ordem + 1

        super().save(*args, **kwargs)


class PastaRecente(models.Model):
    """
    Tabela para pastas recentemente acessadas (máximo 10 por usuário)
    Implementa comportamento de fila (FIFO)
    """
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pastas_recentes"
    )
    pasta = models.ForeignKey(
        Pasta,
        on_delete=models.CASCADE,
        related_name="acessada_recentemente"
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="pastas_recentes",
        null=True,
        blank=True
    )
    acessado_em = models.DateTimeField(auto_now=True)  # Atualiza sempre que é acessado

    class Meta:
        db_table = 'cloud_pasta_recente'
        verbose_name = 'Pasta Recente'
        verbose_name_plural = 'Pastas Recentes'
        unique_together = ['usuario', 'pasta']  # Um registro por pasta por usuário
        ordering = ['-acessado_em']

    def __str__(self):
        return f"{self.usuario.username} - {self.pasta.nome} (acessado em {self.acessado_em})"

    def save(self, *args, **kwargs):
        # Se é um novo acesso
        if not self.pk:
            # Verifica se já tem 10 pastas recentes
            pastas_count = PastaRecente.objects.filter(usuario=self.usuario).count()
            if pastas_count >= 10:
                # Remove a mais antiga (menor data de acesso)
                mais_antiga = PastaRecente.objects.filter(
                    usuario=self.usuario
                ).order_by('acessado_em').first()
                if mais_antiga:
                    mais_antiga.delete()

        super().save(*args, **kwargs)

    @classmethod
    def registrar_acesso(cls, usuario, pasta, empresa):
        """
        Método para registrar acesso a uma pasta
        Se já existe, atualiza a data de acesso
        Se não existe, cria novo (e remove o mais antigo se necessário)
        """
        try:
            # Tenta encontrar registro existente
            recente, created = cls.objects.get_or_create(
                usuario=usuario,
                pasta=pasta,
                defaults={'empresa': empresa}
            )
            if not created:
                # Se já existe, apenas salva para atualizar acessado_em
                recente.save()
            return recente
        except Exception as e:
            print(f"Erro ao registrar acesso: {e}")
            return None
