from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return super().update(deletado_em=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deletado_em__isnull=True)

    def deleted(self):
        return self.filter(deletado_em__isnull=False)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()
