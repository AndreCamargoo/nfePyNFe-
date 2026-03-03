from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from app.core.middleware import get_current_user


class AuditModel(models.Model):
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created"
    )

    updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated"
    )

    deleted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_deleted"
    )

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    # SAVE (create/update)
    def save(self, *args, **kwargs):
        user = get_current_user()

        if (
            user
            and hasattr(user, "is_authenticated")
            and user.is_authenticated
        ):
            if not self.pk:
                self.created_by = user
            self.updated_by = user

        super().save(*args, **kwargs)

    # SOFT DELETE
    def soft_delete(self):
        if self.deleted_at:
            return  # já está deletado

        user = get_current_user()

        self.deleted_at = timezone.now()

        if (
            user
            and hasattr(user, "is_authenticated")
            and user.is_authenticated
        ):
            self.deleted_by = user

        self.save()

    # RESTORE
    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save()

    # BLOQUEAR DELETE FÍSICO
    def delete(self, *args, **kwargs):
        raise Exception(
            "Delete físico não permitido. Use soft_delete()."
        )