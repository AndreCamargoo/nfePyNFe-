from django.db import models
from django.contrib.auth.models import User

from empresa.models import Empresa


# Sistemas que a API oferece.
class Sistema(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nome


# Relação de quais sistemas uma empresa utiliza.
class EmpresaSistema(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="sistemas")
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE, related_name="empresas")
    ativo = models.BooleanField(default=True)

    class Meta:
        unique_together = ("empresa", "sistema")

    def __str__(self):
        return f"{self.empresa.razao_social} - {self.sistema.nome}"


# Rotas que um sistema pode ter, para controle de permissões.
class RotaSistema(models.Model):
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE, related_name="rotas")
    nome = models.CharField(max_length=100)
    path = models.CharField(max_length=200)  # Exemplo: "/nfes/resumo/"
    metodo = models.CharField(max_length=10, default="GET")  # GET, POST, PUT, DELETE
    descricao = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.sistema.nome} - {self.nome} ({self.metodo} {self.path})"


class GrupoRotaSistema(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="grupos_rotas")
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE, related_name="grupos_rotas")
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    rotas = models.ManyToManyField(RotaSistema, related_name="grupos")

    def __str__(self):
        return f"{self.sistema.nome} - {self.nome}"
