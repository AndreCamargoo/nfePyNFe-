from django.contrib.auth.models import User
from django.db import models


ESTADOS_CHOICES = (
    ('AC', 'Acre'),
    ('AL', 'Alagoas'),
    ('AP', 'Amapá'),
    ('AM', 'Amazonas'),
    ('BA', 'Bahia'),
    ('CE', 'Ceará'),
    ('DF', 'Distrito Federal'),
    ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'),
    ('MA', 'Maranhão'),
    ('MT', 'Mato Grosso'),
    ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'),
    ('PA', 'Pará'),
    ('PB', 'Paraíba'),
    ('PR', 'Paraná'),
    ('PE', 'Pernambuco'),
    ('PI', 'Piauí'),
    ('RJ', 'Rio de Janeiro'),
    ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'),
    ('RO', 'Rondônia'),
    ('RR', 'Roraima'),
    ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'),
    ('SE', 'Sergipe'),
    ('TO', 'Tocantins'),
)

STATUS_CHOICES = (
    ('1', 'Ativo'),
    ('2', 'Inativo'),
)


class Empresa(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='empresas')
    matriz_filial = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='filiais')
    razao_social = models.CharField(max_length=200)
    documento = models.CharField(max_length=18)
    ie = models.CharField(max_length=15)
    uf = models.CharField(max_length=2, choices=ESTADOS_CHOICES)
    senha = models.CharField(max_length=255)
    file = models.FileField(upload_to='certificados/', null=True, blank=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.razao_social


class HistoricoNSU(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='historico_empresa')
    nsu = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.empresa.razao_social
