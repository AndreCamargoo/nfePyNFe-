from django.db import models


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


class Lead(models.Model):
    """Refere-se a 'LEADS'"""
    empresa = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=20, blank=True, null=True)
    cnes = models.CharField(max_length=20, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=2, blank=True, null=True)
    segmento = models.CharField(max_length=100, blank=True, null=True)
    classificacao = models.CharField(max_length=50, default='Não Cliente')
    origem = models.CharField(max_length=100, blank=True, null=True)

    # ManyToMany usando string references ou IDs.
    # Para simplificar a compatibilidade com o frontend que enviava nomes,
    # vamos usar ManyToMany real aqui.
    empresas_grupo = models.ManyToManyField(Company, blank=True, related_name='leads')
    produtos_interesse = models.ManyToManyField(Product, blank=True, related_name='interested_leads')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Campo para Soft Delete
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.empresa


class Contact(models.Model):
    """Refere-se a 'contatos' dentro de LEADS"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='contatos')
    nome = models.CharField(max_length=255)
    setor = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.nome} - {self.lead.empresa}"