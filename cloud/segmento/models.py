from django.db import models


class StatusChoices(models.TextChoices):
    ATIVO = '1', 'Ativo'
    INATIVO = '2', 'Inativo'


class TipoSegmentoChoices(models.TextChoices):
    ANUAL = '1', 'Anual'
    MENSAL = '2', 'Mensal'


class Segmento(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=1, choices=TipoSegmentoChoices.choices, default=TipoSegmentoChoices.ANUAL)
    status = models.CharField(max_length=1, choices=StatusChoices.choices, default=StatusChoices.ATIVO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cloud_segmento'
        verbose_name = 'Segmento'
        verbose_name_plural = 'Segmentos'

    def __str__(self):
        return self.nome
