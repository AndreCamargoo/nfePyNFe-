# app/utils/storage_backends.py
import os
import hashlib
import time
import uuid
from django.conf import settings
from django.core.files.storage import FileSystemStorage as BaseFileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage


# ==================== FileSystemStorage Local ====================
class FileSystemStorage(BaseFileSystemStorage):
    """
    FileSystemStorage customizado que evita sobrescrita de arquivos locais
    """

    def get_available_name(self, name, max_length=None):
        """
        Gera um nome único para o arquivo para evitar sobrescrita
        """
        if self.exists(name):
            dir_name, file_name = os.path.split(name)
            file_root, file_ext = os.path.splitext(file_name)

            timestamp = int(time.time() * 1000)
            unique_hash = hashlib.md5(
                f"{file_root}_{timestamp}_{uuid.uuid4()}".encode()
            ).hexdigest()[:8]

            new_name = f"{file_root}_{unique_hash}{file_ext}"
            name = os.path.join(dir_name, new_name)

        return super().get_available_name(name, max_length)


# ==================== S3Storage SIMPLIFICADO ====================
class S3Storage(S3Boto3Storage):
    """
    Storage para Amazon S3 (versão simplificada para compatibilidade)
    """

    def __init__(self, *args, **kwargs):
        # Configurações do S3
        kwargs['bucket_name'] = settings.AWS_BUCKET
        kwargs['access_key'] = settings.AWS_ACCESS_KEY_ID
        kwargs['secret_key'] = settings.AWS_SECRET_ACCESS_KEY
        kwargs['region_name'] = settings.AWS_DEFAULT_REGION

        # Para buckets que não suportam ACLs
        kwargs['object_parameters'] = {
            'CacheControl': 'max-age=86400',
        }

        # Para URLs públicas
        kwargs['querystring_auth'] = False

        super().__init__(*args, **kwargs)

    def get_available_name(self, name, max_length=None):
        """
        Gera um nome único para o arquivo no S3
        """
        dir_name, file_name = os.path.split(name)
        file_root, file_ext = os.path.splitext(file_name)

        timestamp = int(time.time() * 1000)
        unique_hash = hashlib.md5(
            f"{file_root}_{timestamp}_{uuid.uuid4()}".encode()
        ).hexdigest()[:8]

        new_name = f"{file_root}_{unique_hash}{file_ext}"
        return os.path.join(dir_name, new_name)


# ==================== Storage Condicional ====================
class ConditionalStorage:
    """
    Storage que escolhe automaticamente entre S3 e sistema de arquivos local
    """

    def __init__(self):
        self.s3_storage = None
        self.local_storage = None
        self._last_drive_used = None

    def _get_storage(self):
        """
        Retorna o storage ativo baseado na configuração
        """
        if getattr(settings, 'AWS_USE_S3_UPLOAD', False):
            if self.s3_storage is None:
                self.s3_storage = S3Storage()
            return self.s3_storage
        else:
            if self.local_storage is None:
                self.local_storage = FileSystemStorage()
            return self.local_storage

    def save(self, name, content, max_length=None):
        """
        Salva o arquivo e rastreia onde foi salvo
        """
        storage = self._get_storage()
        saved_name = storage.save(name, content, max_length)

        # Determina o drive usado
        if isinstance(storage, S3Storage):
            self._last_drive_used = '2'  # S3
        else:
            self._last_drive_used = '1'  # Local

        return saved_name

    def get_last_drive_used(self):
        """
        Retorna o último drive usado para salvar
        """
        return self._last_drive_used

    def get_available_name(self, name, max_length=None):
        """Delega para o storage ativo"""
        storage = self._get_storage()
        return storage.get_available_name(name, max_length)

    def url(self, name):
        """Delega para o storage ativo"""
        storage = self._get_storage()
        return storage.url(name)

    def exists(self, name):
        """Delega para o storage ativo"""
        storage = self._get_storage()
        return storage.exists(name)

    def size(self, name):
        """Delega para o storage ativo"""
        storage = self._get_storage()
        return storage.size(name)

    def __getattr__(self, name):
        """
        Delega qualquer chamada de método para o storage ativo
        """
        storage = self._get_storage()
        return getattr(storage, name)


# ==================== Instância Global ====================
conditional_storage = ConditionalStorage()
