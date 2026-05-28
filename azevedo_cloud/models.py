import uuid
from django.db import models
from django.contrib.auth.models import User
from empresa.models import Empresa, Funcionario


class Segmento(models.Model):
    """
    Representa a arquitetura raiz (Pasta principal).
    Ex: "Auditoria Contábil 2024" ou "Circularização 2024 - Empresa XPTO"
    """
    VALIDADE_CHOICES = [
        ('1_ano', 'Ciclo Anual'),
        ('mensal', 'Ciclo Mensal'),
    ]

    # A empresa dona do sistema (Auditoria)
    empresa_auditoria = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name='segmentos_criados',
        help_text="Empresa de auditoria proprietária da estrutura"
    )

    nome = models.CharField(max_length=255, help_text="Nome da pasta raiz")
    ano = models.IntegerField(help_text="Ano de referência (Obrigatório)")
    validade = models.CharField(max_length=20, choices=VALIDADE_CHOICES, default='1_ano')
    is_circ = models.BooleanField(default=False, help_text="Indica se é uma raiz gerada via Circularização")

    # Múltiplos clientes podem ter acesso a este segmento (Vínculos Multi-Clientes)
    clientes = models.ManyToManyField(Empresa, related_name='segmentos_vinculados', blank=True)

    # Funcionários internos (Suporte/Administrativo) que podem visualizar/editar esta raiz
    responsaveis = models.ManyToManyField(Funcionario, related_name='segmentos_responsaveis', blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Segmento"
        verbose_name_plural = "Segmentos"
        constraints = [
            # Trava para não criar Segmentos (Pastas de Auditoria) com o mesmo NOME e ANO para a mesma Auditoria
            models.UniqueConstraint(
                fields=['empresa_auditoria', 'nome', 'ano'],
                condition=models.Q(is_circ=False),
                name='unique_segmento_auditoria_por_ano'
            )
        ]

    def __str__(self):
        tipo = "CIRC" if self.is_circ else "AUD"
        return f"[{tipo}] {self.nome} ({self.ano})"


class Subpasta(models.Model):
    """
    Subpastas criadas dentro de um Segmento (Ex: "Contratos", "Extratos").
    No caso de circularização, também recebe a Categoria (Ex: "CCF", "CCA").
    """
    segmento = models.ForeignKey(Segmento, on_delete=models.CASCADE, related_name='subpastas')
    nome = models.CharField(max_length=255)
    categoria_circ = models.CharField(max_length=50, null=True, blank=True, help_text="Ex: CCF, CCA, CCB")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subpasta"
        verbose_name_plural = "Subpastas"

    def __str__(self):
        return f"{self.segmento.nome} -> {self.nome}"


class Arquivo(models.Model):
    """
    Representa o documento/arquivo depositado no Cofre.
    """
    subpasta = models.ForeignKey(Subpasta, on_delete=models.CASCADE, related_name='arquivos')

    # CRÍTICO: Mesmo que o Segmento seja compartilhado com 5 clientes,
    # o arquivo físico tem que ter dono para não misturar documentos de empresas diferentes.
    cliente = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='arquivos_cliente')

    # Usuário que fez o upload (pode ser o cliente, um auditor, ou nulo se for via Link Visitante)
    enviado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='arquivos_enviados')
    nome_remetente = models.CharField(max_length=150, help_text="Nome de quem enviou (útil para links externos sem login)")

    nome_arquivo = models.CharField(max_length=255)
    arquivo = models.FileField(upload_to='azevedo_cloud/arquivos/%Y/%m/')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Arquivo"
        verbose_name_plural = "Arquivos"

    def __str__(self):
        return self.nome_arquivo


class Circularizacao(models.Model):
    """
    Gera e controla o Link Externo para captar arquivos de terceiros (Circularização).
    """
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
    ]

    id_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, help_text="UUID usado na URL pública")

    # A circularização cria uma estrutura de pasta (Segmento) 1 para 1
    segmento = models.OneToOneField(Segmento, on_delete=models.CASCADE, related_name='circularizacao_link')

    # Empresa cliente alvo da circularização
    cliente = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='circularizacoes')

    # Quem da equipe interna está responsável por essa circularização
    responsavel = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, related_name='circularizacoes_responsaveis')

    ano = models.IntegerField(help_text="Ano da circularização (Obrigatório)")
    senha = models.CharField(max_length=20, help_text="Código de segurança para abrir o link (Ex: ABC123)")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ativo')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Circularização"
        verbose_name_plural = "Circularizações"
        # Trava para impedir a criação de mais de uma circularização para o mesmo cliente no mesmo ano
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'ano'],
                name='unique_circularizacao_por_cliente_ano'
            )
        ]

    def __str__(self):
        return f"Link {self.ano} - {self.cliente.razao_social}"
