from django.db import models
from app.core.auditoria_abstrato import AuditModel


class Company(models.Model):
    """Refere-se a 'COMPANIES' (Matriz, Filial, etc)"""
    nome = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class Product(models.Model):
    """Refere-se a 'PRODUCTS'"""
    nome = models.CharField(max_length=255)
    # Relacionamento Opcional: Se um produto pertence a uma empresa do grupo específica
    empresa_grupo = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class Event(models.Model):
    """Refere-se a 'EVENTS'"""
    nome = models.CharField(max_length=255)
    data = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.data})"


class Lead(AuditModel):
    """Refere-se a 'LEADS'"""
    empresa = models.CharField(max_length=500)  # AUMENTADO para 500
    cnpj = models.CharField(max_length=50, blank=True, null=True)  # AUMENTADO para 50
    cnes = models.CharField(max_length=50, blank=True, null=True)  # AUMENTADO para 50
    telefone = models.CharField(max_length=100, blank=True, null=True)  # AUMENTADO para 100
    cidade = models.CharField(max_length=200, blank=True, null=True)  # AUMENTADO para 200
    estado = models.CharField(max_length=2, blank=True, null=True)
    segmento = models.CharField(max_length=200, blank=True, null=True)  # AUMENTADO para 200
    classificacao = models.CharField(max_length=50, default='Não Cliente')
    origem = models.CharField(max_length=200, blank=True, null=True)  # AUMENTADO para 200

    # ManyToMany
    empresas_grupo = models.ManyToManyField(Company, blank=True, related_name='leads')
    produtos_interesse = models.ManyToManyField(Product, blank=True, related_name='interested_leads')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # NOVOS CAMPOS
    apelido = models.CharField(max_length=500, null=True, blank=True)  # AUMENTADO
    cod_nat_jur = models.CharField(max_length=50, null=True, blank=True)  # AUMENTADO
    natureza_juridica = models.CharField(max_length=500, null=True, blank=True)  # AUMENTADO
    observacoes = models.TextField(null=True, blank=True, help_text="Observações gerais sobre o lead")

    def __str__(self):
        return self.empresa


class Contact(AuditModel):
    """Refere-se a 'contatos' dentro de LEADS"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='contatos')
    nome = models.CharField(max_length=500)  # AUMENTADO
    setor = models.CharField(max_length=300, blank=True, null=True)  # AUMENTADO
    email = models.EmailField(blank=True, null=True, max_length=500)  # AUMENTADO
    celular = models.CharField(max_length=100, blank=True, null=True)  # AUMENTADO
    telefone_contato = models.CharField(max_length=100, blank=True, null=True)  # AUMENTADO
    email_extra = models.EmailField(blank=True, null=True, max_length=500)  # AUMENTADO

    def __str__(self):
        return f"{self.nome} - {self.lead.empresa}"


class Cnes(models.Model):
    razao_social = models.CharField(max_length=150)
    fantasia = models.CharField(max_length=150)
    cod_nat_jur = models.CharField(max_length=20)
    natureza_juridica = models.CharField(max_length=150)
    cnes = models.CharField(max_length=50)
    cpf_cnpj = models.CharField(max_length=50)
    tipo_unidade = models.CharField(max_length=150)
    endereco = models.CharField(max_length=255, blank=True, null=True)
    cidade = models.CharField(max_length=200)
    uf = models.CharField(max_length=2)
    telefone = models.CharField(max_length=100, blank=True, null=True)
    faturamento_sus_2020 = models.DecimalField(max_digits=17, decimal_places=2, default=0.00)
    qtde_leitos = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    file = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'cnes'
        indexes = [
            models.Index(fields=['cidade']),
            models.Index(fields=['uf']),
            models.Index(fields=['cnes']),
            models.Index(fields=['cpf_cnpj']),
        ]


class Municipalities(models.Model):
    co_municip = models.CharField(max_length=50, unique=True)
    ds_nome = models.CharField(max_length=200)
    ds_nomepad = models.CharField(max_length=200)
    co_uf = models.CharField(max_length=2)

    class Meta:
        db_table = 'municipalities'

    def __str__(self):
        return f"{self.co_uf} - {self.ds_nome}"
