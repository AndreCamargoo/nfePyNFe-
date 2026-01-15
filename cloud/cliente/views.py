import os
import zipfile
import tempfile

import boto3
from botocore.client import Config

from django.db.models import Sum, Count, Q
from django.core.files.storage import FileSystemStorage

from django.conf import settings
from django.http import FileResponse
from django.utils.text import slugify

from wsgiref.util import FileWrapper
from django.http import StreamingHttpResponse

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from django.db import transaction

from .models import (
    Pasta, Arquivo, Cliente, AdministradorPasta,
    PastaFixada, PastaRecente, TipoDrive, StatusChoices, User
)
from .serializer import (
    PastaModelSerializer, ArquivoModelSerializer, ClienteModelSerializer,
    AdministradorPastaModelSerializer, AdministradorFuncionarioPastaModelSerializer,
    PastaFixadaSerializer, PastaFixadaCreateSerializer, PastaRecenteSerializer,
    AdministradorPastaBulkSerializer, AdministradorPastaSerializer
)

from app.utils import utils
from empresa.models import Empresa
from app.permissions import PodeAcessarRotasFuncionario

from urllib.parse import urljoin
from django.conf import settings


class PastaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    serializer_class = PastaModelSerializer
    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        paginate = self.request.query_params.get("paginate", "false")

        if paginate.lower() in ["true", "1", "yes"]:
            return super().paginate_queryset(queryset)

        return None  # padrão SEM paginação

    def get_queryset(self):
        user = self.request.user
        empresa_id = self.request.query_params.get('empresa')

        # Superusuário - comportamento padrão
        if user.is_superuser:
            if empresa_id:
                # Via AdministradorPasta (se essa é a relação principal)
                pastas_ids = AdministradorPasta.objects.filter(
                    empresa_id=empresa_id
                ).values_list('pasta_id', flat=True).distinct()
                # print(f"Pastas encontradas via AdministradorPasta: {pastas_ids.count()}")

                return Pasta.objects.filter(
                    id__in=pastas_ids,
                    pasta_pai__isnull=True
                )

            else:
                # Se não passou empresa, retorna todas as pastas raiz
                return Pasta.objects.filter(pasta_pai__isnull=True)

        # Usuário comum - comportamento padrão
        try:
            if empresa_id:
                # Se passou empresa, verifica se tem permissão para essa empresa específica
                pastas_administradas = AdministradorPasta.objects.filter(
                    funcionario=user,
                    empresa_id=empresa_id
                )

                if pastas_administradas.exists():
                    # É administrador da empresa especificada
                    pastas_ids = pastas_administradas.values_list('pasta_id', flat=True)
                    return Pasta.objects.filter(
                        id__in=pastas_ids,
                        pasta_pai__isnull=True
                    )
                else:
                    # Verifica se a empresa pertence ao usuário
                    if hasattr(user, 'empresa') and str(user.empresa.id) == empresa_id:
                        return Pasta.objects.filter(
                            clientes_da_pasta__empresa_id=empresa_id,
                            pasta_pai__isnull=True
                        ).distinct()
                    else:
                        # Usuário não tem permissão para acessar pastas desta empresa
                        return Pasta.objects.none()
            else:
                # Comportamento padrão - pastas que o usuário tem acesso (sem filtrar por empresa)
                pastas_administradas = AdministradorPasta.objects.filter(funcionario=user)

                if pastas_administradas.exists():
                    # Retorna todas as pastas que administra
                    pastas_ids = pastas_administradas.values_list('pasta_id', flat=True)
                    return Pasta.objects.filter(
                        id__in=pastas_ids,
                        pasta_pai__isnull=True
                    )
                else:
                    # Retorna pastas da empresa do usuário
                    if hasattr(user, 'empresa'):
                        return Pasta.objects.filter(
                            clientes_da_pasta__empresa=user.empresa,
                            pasta_pai__isnull=True
                        ).distinct()
                    else:
                        return Pasta.objects.none()

        except Exception as e:
            print(f"Erro ao buscar pastas: {e}")
            return Pasta.objects.none()


class PastaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Pasta.objects.all()
    serializer_class = PastaModelSerializer

    def perform_destroy(self, instance):
        instance.delete(user=self.request.user)


class SubPastaListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    serializer_class = PastaModelSerializer
    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        paginate = self.request.query_params.get("paginate", "false")

        if paginate.lower() in ["true", "1", "yes"]:
            return super().paginate_queryset(queryset)

        return None  # padrão SEM paginação

    def get_queryset(self):
        user = self.request.user
        empresa_id = self.request.query_params.get('empresa')

        # Superusuário - comportamento padrão
        if user.is_superuser:
            if empresa_id:
                # Via AdministradorPasta (se essa é a relação principal)
                pastas_ids = AdministradorPasta.objects.filter(
                    empresa_id=empresa_id
                ).values_list('pasta_id', flat=False).distinct()
                # print(f"Pastas encontradas via AdministradorPasta: {pastas_ids.count()}")

                return Pasta.objects.filter(
                    id__in=pastas_ids,
                    pasta_pai__isnull=False
                )

            else:
                # Se não passou empresa, retorna todas as pastas raiz
                return Pasta.objects.filter(pasta_pai__isnull=False)

        # Usuário comum - comportamento padrão
        try:
            if empresa_id:
                # Se passou empresa, verifica se tem permissão para essa empresa específica
                pastas_administradas = AdministradorPasta.objects.filter(
                    funcionario=user,
                    empresa_id=empresa_id
                )

                if pastas_administradas.exists():
                    # É administrador da empresa especificada
                    pastas_ids = pastas_administradas.values_list('pasta_id', flat=False)
                    return Pasta.objects.filter(
                        id__in=pastas_ids,
                        pasta_pai__isnull=False
                    )
                else:
                    # Verifica se a empresa pertence ao usuário
                    if hasattr(user, 'empresa') and str(user.empresa.id) == empresa_id:
                        return Pasta.objects.filter(
                            clientes_da_pasta__empresa_id=empresa_id,
                            pasta_pai__isnull=False
                        ).distinct()
                    else:
                        # Usuário não tem permissão para acessar pastas desta empresa
                        return Pasta.objects.none()
            else:
                # Comportamento padrão - pastas que o usuário tem acesso (sem filtrar por empresa)
                pastas_administradas = AdministradorPasta.objects.filter(funcionario=user)

                if pastas_administradas.exists():
                    # Retorna todas as pastas que administra
                    pastas_ids = pastas_administradas.values_list('pasta_id', flat=False)
                    return Pasta.objects.filter(
                        id__in=pastas_ids,
                        pasta_pai__isnull=False
                    )
                else:
                    # Retorna pastas da empresa do usuário
                    if hasattr(user, 'empresa'):
                        return Pasta.objects.filter(
                            clientes_da_pasta__empresa=user.empresa,
                            pasta_pai__isnull=False
                        ).distinct()
                    else:
                        return Pasta.objects.none()

        except Exception as e:
            print(f"Erro ao buscar pastas: {e}")
            return Pasta.objects.none()


class SubPastaDirectListAPIView(generics.ListAPIView):
    """
    Retorna APENAS as subpastas DIRETAS (filhas imediatas) de uma pasta específica
    Onde pasta_pai = pk da URL
    """
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    serializer_class = PastaModelSerializer
    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        """Aplica a mesma lógica de paginação da view original"""
        paginate = self.request.query_params.get("paginate", "false")

        if paginate.lower() in ["true", "1", "yes"]:
            return super().paginate_queryset(queryset)

        return None  # padrão SEM paginação

    def get_queryset(self):
        """
        Retorna APENAS as subpastas diretas onde pasta_pai = pk da URL
        """
        pasta_pai_id = self.kwargs['pk']
        user = self.request.user
        empresa_id = self.request.query_params.get('empresa')

        # Query inicial: subpastas onde pasta_pai = pk
        queryset = Pasta.objects.filter(
            pasta_pai_id=pasta_pai_id,
            status='1'  # Apenas ativas
        )

        # Filtra por permissões do usuário
        queryset = self._filtrar_por_permissao(queryset, user, empresa_id)

        # Adiciona anotações para cada subpasta
        for pasta in queryset:
            pasta.individual_size = pasta.get_individual_size()
            pasta.individual_files_count = pasta.get_immediate_files_count()

        return queryset

    def _filtrar_por_permissao(self, queryset, user, empresa_id):
        """
        Filtra as subpastas baseado nas permissões do usuário
        """
        # Superusuário - acessa todas
        if user.is_superuser:
            return queryset

        # Usuário comum - filtra pastas que tem acesso
        if empresa_id:
            # Pastas que o usuário administra nesta empresa
            pastas_administradas = AdministradorPasta.objects.filter(
                funcionario=user,
                empresa_id=empresa_id
            ).values_list('pasta_id', flat=True)

            # Pastas da empresa do usuário (se for a mesma)
            if hasattr(user, 'empresa') and str(user.empresa.id) == empresa_id:
                pastas_empresa = Pasta.objects.filter(
                    clientes_da_pasta__empresa_id=empresa_id
                ).values_list('id', flat=True)
                pasta_ids = list(pastas_administradas) + list(pastas_empresa)
            else:
                pasta_ids = list(pastas_administradas)
        else:
            # Pastas que o usuário administra (sem filtro de empresa)
            pastas_administradas = AdministradorPasta.objects.filter(
                funcionario=user
            ).values_list('pasta_id', flat=True)

            # Pastas da empresa do usuário
            if hasattr(user, 'empresa'):
                pastas_empresa = Pasta.objects.filter(
                    clientes_da_pasta__empresa=user.empresa
                ).values_list('id', flat=True)
                pasta_ids = list(pastas_administradas) + list(pastas_empresa)
            else:
                pasta_ids = list(pastas_administradas)

        # Filtra o queryset pelas pastas que o usuário tem acesso
        return queryset.filter(id__in=pasta_ids)


class ArquivoListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = Arquivo.objects.all()
    serializer_class = ArquivoModelSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """Filtra arquivos por empresa do usuário logado"""
        queryset = super().get_queryset()

        # Filtra por empresa do usuário
        if hasattr(self.request.user, 'empresa'):
            queryset = queryset.filter(empresa=self.request.user.empresa)

        # Filtros opcionais via query params
        pasta_id = self.request.query_params.get('pasta_id')
        if pasta_id:
            queryset = queryset.filter(pasta_id=pasta_id)

        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)

        # Filtro por drive
        drive = self.request.query_params.get('drive')
        if drive in [TipoDrive.LOCAL, TipoDrive.S3]:
            queryset = queryset.filter(drive=drive)

        # Apenas arquivos ativos
        queryset = queryset.filter(status='1')

        # Ordenação
        ordenacao = self.request.query_params.get('ordenacao', '-criado_em')
        if ordenacao in ['criado_em', '-criado_em', 'nome', '-nome', 'tamanho', '-tamanho']:
            queryset = queryset.order_by(ordenacao)

        return queryset

    def perform_create(self, serializer):
        """Cria um novo arquivo"""
        try:
            instance = serializer.save()
            return instance
        except Exception as e:
            # Log do erro já foi feito no serializer
            raise


class ArquivoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = Arquivo.objects.all()
    serializer_class = ArquivoModelSerializer
    parser_classes = [MultiPartParser, FormParser]

    def perform_destroy(self, instance):
        instance.delete(user=self.request.user)


class ArquivoListByPastaAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    serializer_class = ArquivoModelSerializer
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        pasta_id = self.kwargs['pasta_id']
        return Arquivo.objects.filter(pasta_id=pasta_id)


class ArquivoListByDriveAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    serializer_class = ArquivoModelSerializer
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        drive = self.kwargs.get('drive')

        if drive not in [TipoDrive.LOCAL, TipoDrive.S3]:
            return Arquivo.objects.none()

        queryset = Arquivo.objects.filter(
            status='1',
            drive=drive
        )

        # Filtra por empresa do usuário
        if hasattr(self.request.user, 'empresa'):
            queryset = queryset.filter(empresa=self.request.user.empresa)

        return queryset


class EstatisticasDriveAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]

    def get(self, request):
        # Filtra por empresa do usuário
        queryset = Arquivo.objects.filter(status='1')

        if hasattr(request.user, 'empresa'):
            queryset = queryset.filter(empresa=request.user.empresa)

        # Estatísticas por drive
        stats_by_drive = queryset.values('drive').annotate(
            total_arquivos=Count('id'),
            total_tamanho=Sum('tamanho')
        ).order_by('drive')

        # Formata as estatísticas
        formatted_stats = []
        total_arquivos = 0
        total_tamanho_bytes = 0

        for stat in stats_by_drive:
            tamanho_mb = (stat['total_tamanho'] or 0) / (1024 * 1024)

            drive_info = {
                'drive': stat['drive'],
                'drive_display': TipoDrive(stat['drive']).label,
                'total_arquivos': stat['total_arquivos'],
                'total_tamanho_bytes': stat['total_tamanho'] or 0,
                'total_tamanho_mb': round(tamanho_mb, 2),
                'total_tamanho_gb': round(tamanho_mb / 1024, 2)
            }
            formatted_stats.append(drive_info)

            total_arquivos += stat['total_arquivos']
            total_tamanho_bytes += stat['total_tamanho'] or 0

        total_tamanho_mb = total_tamanho_bytes / (1024 * 1024)

        return Response({
            'por_drive': formatted_stats,
            'resumo': {
                'total_arquivos': total_arquivos,
                'total_tamanho_bytes': total_tamanho_bytes,
                'total_tamanho_mb': round(total_tamanho_mb, 2),
                'total_tamanho_gb': round(total_tamanho_mb / 1024, 2)
            },
            'drives_disponiveis': [
                {'code': TipoDrive.LOCAL, 'display': TipoDrive.LOCAL.label},
                {'code': TipoDrive.S3, 'display': TipoDrive.S3.label}
            ]
        })


class DownloadArquivoAPIView(APIView):
    """
    View para download de um arquivo individual
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, arquivo_id):
        try:
            # Busca o arquivo
            arquivo = Arquivo.objects.filter(
                id=arquivo_id,
                status=StatusChoices.ATIVO
            ).first()

            # Verifica permissão
            if not self._tem_permissao(request.user, arquivo):
                return Response(
                    {'error': 'Você não tem permissão para acessar este arquivo'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Se o arquivo está no S3
            if arquivo.drive == TipoDrive.S3:
                return self._download_s3(arquivo)
            else:
                return self._download_local(request, arquivo)

        except Arquivo.DoesNotExist:
            return Response(
                {'error': 'Arquivo não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Erro ao fazer download: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _tem_permissao(self, user, arquivo):
        """Verifica se o usuário tem permissão para acessar o arquivo"""
        # Verifica se o arquivo pertence à empresa do usuário
        if hasattr(user, 'empresa') and user.empresa:
            return arquivo.empresa == user.empresa

        # Verifica se o usuário é administrador da pasta
        from .models import AdministradorPasta
        return AdministradorPasta.objects.filter(
            funcionario=user,
            pasta=arquivo.pasta,
            empresa=arquivo.empresa
        ).exists()

    def _download_local_arquivo(self, arquivo):

        # Usa diretamente o FileSystemStorage local
        storage = FileSystemStorage()

        try:
            file_path = storage.path(arquivo.arquivo.name)

            if not os.path.exists(file_path):
                return Response(
                    {"error": "Arquivo não encontrado no servidor local"},
                    status=404
                )

            file_handle = open(file_path, "rb")
            response = FileResponse(file_handle)
            response["Content-Disposition"] = f'attachment; filename=\"{arquivo.nome}\"'
            return response

        except Exception as e:
            return Response(
                {"error": f"Erro no download local: {str(e)}"},
                status=500
            )

    def _download_local(self, request, arquivo):
        """
        Retorna uma URL HTTP (mesmo padrão do S3) para arquivos locais.
        Não retorna paths absolutos.
        """
        try:
            # Garante MEDIA_URL terminando com '/'
            media_url = settings.MEDIA_URL or '/media/'
            if not media_url.endswith('/'):
                media_url = media_url + '/'

            # Se MEDIA_URL for relativo (p.ex. '/media/'), build_absolute_uri resolve a URL completa
            # Usa apenas o nome armazenado no campo (arquivo.arquivo.name)
            relative_url = urljoin(media_url, arquivo.arquivo.name)

            # Gera URL absoluta baseada na requisição
            absolute_url = request.build_absolute_uri(relative_url)

            return Response({
                "url": absolute_url,
                "filename": arquivo.nome_original or arquivo.nome,
                "expires_in": 3600,
                "drive": "local"
            })

        except Exception as e:
            return Response(
                {"error": f"Erro no download local: {str(e)}"},
                status=500
            )

    def _download_s3(self, arquivo):
        """Download de arquivo do S3"""
        try:
            # Configura cliente S3
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_DEFAULT_REGION,
                config=Config(signature_version='s3v4')
            )

            # Gera URL pré-assinada para download
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_BUCKET,
                    'Key': arquivo.arquivo.name
                },
                ExpiresIn=3600  # URL válida por 1 hora
            )

            return Response({
                'url': url,
                'filename': arquivo.nome_original or arquivo.nome,
                'expires_in': 3600,
                "drive": "s3"
            })

        except Exception as e:
            return Response(
                {'error': f'Erro ao gerar URL do S3: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DownloadPastaAPIView(APIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]

    def get(self, request, pasta_id):
        try:
            pasta = Pasta.objects.get(id=pasta_id)

            arquivos = Arquivo.objects.filter(
                pasta=pasta,
                status=StatusChoices.ATIVO,
            )

            if not arquivos.exists():
                return Response({"error": "Pasta vazia"}, status=404)

            return self._stream_zip(pasta, arquivos)

        except Pasta.DoesNotExist:
            return Response({"error": "Pasta não encontrada"}, status=404)

        except Exception as e:
            return Response({"error": f"Erro: {e}"}, status=500)

    def _nome_unico(self, nome, usados):
        """
        Garante que o nome não seja duplicado dentro do ZIP.
        Se já existir, adiciona (1), (2), etc.
        """
        if nome not in usados:
            usados.add(nome)
            return nome

        base, ext = os.path.splitext(nome)
        contador = 1

        novo_nome = f"{base} ({contador}){ext}"

        while novo_nome in usados:
            contador += 1
            novo_nome = f"{base} ({contador}){ext}"

        usados.add(novo_nome)
        return novo_nome

    # Caminho real para arquivos locais
    @staticmethod
    def _get_local_file_path(arquivo):
        storage = FileSystemStorage()
        return storage.path(arquivo.arquivo.name)

    def _stream_zip(self, pasta, arquivos):
        temp = tempfile.TemporaryFile()
        nomes_usados = set()

        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as zipf:

            for arquivo in arquivos:

                nome_final = arquivo.nome_original or arquivo.nome

                # Se não tiver extensão, adiciona
                if not os.path.splitext(nome_final)[1]:
                    nome_final = f"{nome_final}.{arquivo.extensao}"

                # Garante nome único
                nome_final = self._nome_unico(nome_final, nomes_usados)

                # 🔥 DECIDE SE É LOCAL OU S3
                if arquivo.drive == TipoDrive.S3:
                    try:
                        self._add_s3_to_zip(zipf, arquivo, nome_final)
                    except Exception as e:
                        print(f"Erro S3 ({arquivo.id}):", e)
                    continue

                # 🔥 ARQUIVO LOCAL
                try:
                    raw_path = self._get_local_file_path(arquivo)
                    local_path = os.path.normpath(raw_path)

                    if os.path.exists(local_path):
                        zipf.write(local_path, nome_final)
                    else:
                        print("Arquivo local não encontrado:", local_path)

                except Exception as e:
                    print("Erro ao compactar local:", e)
                    continue

        temp.seek(0)

        response = StreamingHttpResponse(
            FileWrapper(temp),
            content_type="application/zip"
        )

        zip_name = f"{slugify(pasta.nome)}.zip"
        response["Content-Disposition"] = f'attachment; filename=\"{zip_name}\"'
        # Streaming — sem necessidade de Content-Length

        return response

    def _add_s3_to_zip(self, zipf, arquivo, nome_final):
        try:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_DEFAULT_REGION
            )

            obj = s3.get_object(
                Bucket=settings.AWS_BUCKET,
                Key=arquivo.arquivo.name
            )

            zipf.writestr(nome_final, obj["Body"].read())

        except Exception as e:
            print(f"[S3] Erro ao adicionar {arquivo.nome}: {e}")


class DownloadMultiplosArquivosAPIView(APIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]

    def post(self, request):
        ids = request.data.get("ids", [])

        if not isinstance(ids, list) or not ids:
            return Response({"detail": "Envie uma lista de IDs de arquivos."}, status=400)

        arquivos = Arquivo.objects.filter(id__in=ids, status=StatusChoices.ATIVO)

        if not arquivos.exists():
            return Response({"detail": "Nenhum arquivo encontrado."}, status=404)

        return self._stream_zip(arquivos)

    # ----------- Mesmo método usado no DownloadPastaAPIView -----------
    def _nome_unico(self, nome, usados):
        if nome not in usados:
            usados.add(nome)
            return nome

        base, ext = os.path.splitext(nome)
        contador = 1

        novo_nome = f"{base} ({contador}){ext}"

        while novo_nome in usados:
            contador += 1
            novo_nome = f"{base} ({contador}){ext}"

        usados.add(novo_nome)
        return novo_nome

    @staticmethod
    def _get_local_file_path(arquivo):
        storage = FileSystemStorage()
        return storage.path(arquivo.arquivo.name)

    # ---------------- STREAM ZIP (idêntico ao do DownloadPasta) ----------------
    def _stream_zip(self, arquivos):
        temp = tempfile.TemporaryFile()
        nomes_usados = set()

        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as zipf:

            for arquivo in arquivos:

                nome_final = arquivo.nome_original or arquivo.nome

                # Se não tiver extensão
                if not os.path.splitext(nome_final)[1]:
                    nome_final = f"{nome_final}.{arquivo.extensao}"

                # Nome único no ZIP
                nome_final = self._nome_unico(nome_final, nomes_usados)

                # ----- S3 -----
                if arquivo.drive == TipoDrive.S3:
                    try:
                        self._add_s3_to_zip(zipf, arquivo, nome_final)
                    except Exception as e:
                        print(f"[S3] Erro arquivo {arquivo.id}:", e)
                    continue

                # ----- LOCAL -----
                try:
                    raw_path = self._get_local_file_path(arquivo)
                    local_path = os.path.normpath(raw_path)

                    if os.path.exists(local_path):
                        zipf.write(local_path, nome_final)
                    else:
                        print("Arquivo local não encontrado:", local_path)

                except Exception as e:
                    print("Erro ao compactar local:", e)
                    continue

        temp.seek(0)

        response = StreamingHttpResponse(
            FileWrapper(temp),
            content_type="application/zip"
        )

        response["Content-Disposition"] = 'attachment; filename="arquivos_selecionados.zip"'

        return response

    # ----------- Igual ao da Pasta -----------
    def _add_s3_to_zip(self, zipf, arquivo, nome_final):
        try:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_DEFAULT_REGION
            )

            obj = s3.get_object(
                Bucket=settings.AWS_BUCKET,
                Key=arquivo.arquivo.name
            )

            zipf.writestr(nome_final, obj["Body"].read())

        except Exception as e:
            print(f"[S3] Erro ao adicionar {arquivo.nome}: {e}")


class ClienteListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = Cliente.objects.all()
    serializer_class = ClienteModelSerializer


class ClienteRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()
    serializer_class = ClienteModelSerializer


class AdministradorPastaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = AdministradorPasta.objects.all()
    serializer_class = AdministradorPastaModelSerializer


class AdministradorPastaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdministradorPastaModelSerializer
    queryset = AdministradorPasta.objects.all()


class AdministradorPastaListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdministradorPastaSerializer

    def get_queryset(self):
        pasta_id = self.kwargs['pasta_id']
        return AdministradorPasta.objects.filter(pasta_id=pasta_id).select_related('empresa', 'funcionario')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # Agrupa por empresa para facilitar o frontend
        empresas = {}
        for item in serializer.data:
            empresa_id = item['empresa']['id']
            if empresa_id not in empresas:
                empresas[empresa_id] = {
                    'empresa': item['empresa'],
                    'funcionarios': []
                }
            empresas[empresa_id]['funcionarios'].append(item['funcionario'])

        # Também pode retornar listas separadas
        empresas_ids = list(set(item['empresa']['id'] for item in serializer.data))
        funcionarios_ids = list(set(item['funcionario']['id'] for item in serializer.data))

        return Response({
            "permissoes": serializer.data,
            "agrupado": list(empresas.values()),
            "listas": {
                "empresas": empresas_ids,
                "funcionarios": funcionarios_ids
            }
        })


class AdministradorPastaBulkCreateAPIView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdministradorPastaBulkSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        registros = serializer.save()

        return Response({
            "created": len(registros),
            "items": [
                {
                    "empresa": r.empresa.id,
                    "pasta": r.pasta.id,
                    "funcionario": r.funcionario.id
                } for r in registros
            ]
        }, status=201)


class AdministradorPastaBulkUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request, pasta_id, *args, **kwargs):
        """
        Atualiza as permissões de uma pasta
        Payload:
        {
            "empresas": [1, 2, 3],  # IDs das empresas
            "funcionarios": [5, 6, 7]  # IDs dos funcionários
        }
        """
        try:
            pasta = Pasta.objects.get(id=pasta_id)
        except Pasta.DoesNotExist:
            return Response(
                {"error": f"Pasta com ID {pasta_id} não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validação básica
        empresas_ids = request.data.get('empresas', [])
        funcionarios_ids = request.data.get('funcionarios', [])

        if not isinstance(empresas_ids, list) or not isinstance(funcionarios_ids, list):
            return Response(
                {"error": "Empresas e funcionários devem ser listas."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica se as empresas existem
        empresas_count = Empresa.objects.filter(id__in=empresas_ids).count()
        if empresas_count != len(empresas_ids):
            return Response(
                {"error": "Uma ou mais empresas não existem."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica se os funcionários existem
        funcionarios_count = User.objects.filter(id__in=funcionarios_ids).count()
        if funcionarios_count != len(funcionarios_ids):
            return Response(
                {"error": "Um ou mais funcionários não existem."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtém as permissões atuais
        permissoes_atuais = AdministradorPasta.objects.filter(pasta=pasta)

        # Cria um conjunto das combinações atuais para comparação
        combinacoes_atuais = set()
        for permissao in permissoes_atuais:
            combinacoes_atuais.add((permissao.empresa_id, permissao.funcionario_id))

        # Cria um conjunto das novas combinações
        novas_combinacoes = set()
        for empresa_id in empresas_ids:
            for funcionario_id in funcionarios_ids:
                novas_combinacoes.add((empresa_id, funcionario_id))

        # Encontra o que precisa ser removido
        para_remover = combinacoes_atuais - novas_combinacoes
        # Encontra o que precisa ser adicionado
        para_adicionar = novas_combinacoes - combinacoes_atuais

        # Remove permissões que não estão mais na lista
        if para_remover:
            for empresa_id, funcionario_id in para_remover:
                AdministradorPasta.objects.filter(
                    pasta=pasta,
                    empresa_id=empresa_id,
                    funcionario_id=funcionario_id
                ).delete()

        # Adiciona novas permissões
        adicionados = []
        if para_adicionar:
            for empresa_id, funcionario_id in para_adicionar:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                    funcionario = User.objects.get(id=funcionario_id)

                    nova_permissao = AdministradorPasta.objects.create(
                        pasta=pasta,
                        empresa=empresa,
                        funcionario=funcionario
                    )
                    adicionados.append(nova_permissao)
                except Exception as e:
                    # Rollback da transação em caso de erro
                    transaction.set_rollback(True)
                    return Response(
                        {"error": f"Erro ao criar permissão: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        # Monta a resposta
        return Response({
            "message": "Permissões atualizadas com sucesso.",
            "pasta_id": pasta_id,
            "pasta_nome": pasta.nome,
            "stats": {
                "empresas_enviadas": len(empresas_ids),
                "funcionarios_enviados": len(funcionarios_ids),
                "combinacoes_totais": len(novas_combinacoes),
                "removidos": len(para_remover),
                "adicionados": len(para_adicionar),
                "mantidos": len(combinacoes_atuais.intersection(novas_combinacoes))
            },
            "adicionados": [
                {
                    "id": item.id,
                    "empresa": item.empresa_id,
                    "funcionario": item.funcionario_id,
                    "empresa_nome": item.empresa.razao_social,
                    "funcionario_nome": item.funcionario.get_full_name() or item.funcionario.username
                } for item in adicionados
            ]
        }, status=status.HTTP_200_OK)


class PastaListByFuncionarioAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdministradorFuncionarioPastaModelSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        funcionario_id = self.kwargs['funcionario_id']

        # Superusuário vê todas as empresas com pastas
        if user.is_superuser:
            # Retorna apenas registros únicos por empresa
            empresas_ids = AdministradorPasta.objects.values_list('empresa_id', flat=True).distinct()
            return AdministradorPasta.objects.filter(
                empresa_id__in=empresas_ids
            ).select_related('empresa', 'pasta').distinct('empresa_id')

        # Usuário comum - retorna empresas únicas para o funcionário
        try:
            # Primeiro obtém os IDs únicos de empresas
            empresas_ids = AdministradorPasta.objects.filter(
                funcionario_id=funcionario_id
            ).values_list('empresa_id', flat=True).distinct()

            # Retorna um AdministradorPasta por empresa (usando o primeiro encontrado)
            from django.db.models import Min
            admin_pastas_ids = AdministradorPasta.objects.filter(
                funcionario_id=funcionario_id,
                empresa_id__in=empresas_ids
            ).values('empresa_id').annotate(
                min_id=Min('id')
            ).values_list('min_id', flat=True)

            return AdministradorPasta.objects.filter(
                id__in=admin_pastas_ids
            ).select_related('empresa', 'pasta')

        except Exception as e:
            print(f"Erro ao buscar empresas: {e}")
            return AdministradorPasta.objects.none()


class PastaFixadaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PastaFixadaCreateSerializer
        return PastaFixadaSerializer

    def get_queryset(self):
        user = self.request.user
        empresa_id = self.request.query_params.get('empresa_id')

        if not empresa_id:
            return PastaFixada.objects.none()

        return PastaFixada.objects.filter(usuario=user, empresa_id=empresa_id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Verifica se já existe
        pasta = serializer.validated_data['pasta']
        empresa = serializer.validated_data['empresa']
        exists = PastaFixada.objects.filter(
            usuario=request.user,
            pasta=pasta,
            empresa=empresa
        ).exists()

        if exists:
            return Response(
                {'error': 'Esta pasta já está fixada para esta empresa'},
                status=status.HTTP_400_BAD_REQUEST
            )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            PastaFixadaSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )


class PastaFixadaDestroyAPIView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PastaFixadaSerializer

    def get_queryset(self):
        user = self.request.user
        empresa_id = self.request.query_params.get('empresa_id')

        if not empresa_id:
            return PastaFixada.objects.none()

        return PastaFixada.objects.filter(usuario=user, empresa_id=empresa_id)


class PastaFixadaListFilteredAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PastaFixadaSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        return PastaFixada.objects.filter(usuario=user)


class PastaRecenteListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PastaRecenteSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        empresa_id = self.request.query_params.get('empresa_id')

        if not empresa_id:
            return PastaRecente.objects.none()

        return PastaRecente.objects.filter(usuario=user, empresa_id=empresa_id)


class PastaRecenteListFilteredAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PastaRecenteSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        return PastaRecente.objects.filter(usuario=user)


class RegistrarAcessoPastaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pasta_id):
        try:
            pasta = Pasta.objects.get(id=pasta_id)
            user = request.user

            empresa_id = request.data.get('empresa_id')
            empresa = None

            # empresa é OPCIONAL
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                except Empresa.DoesNotExist:
                    return Response({'error': 'Empresa não encontrada'}, status=404)

            # PERMISSÃO
            if not user.is_superuser:

                # Caso não exista empresa, libera desde que tenha acesso à pasta
                if empresa is None:
                    tem_permissao = AdministradorPasta.objects.filter(
                        funcionario=user,
                        pasta=pasta
                    ).exists()
                else:
                    tem_permissao = (
                        AdministradorPasta.objects.filter(
                            funcionario=user,
                            pasta=pasta,
                            empresa=empresa
                        ).exists()
                        or
                        Cliente.objects.filter(
                            empresa=empresa,
                            pastas=pasta
                        ).exists()
                        and hasattr(user, 'empresa')
                        and user.empresa.id == empresa.id
                    )

                if not tem_permissao:
                    return Response(
                        {'error': 'Você não tem permissão para acessar esta pasta'},
                        status=403
                    )

            # REGISTRAR ACESSO — empresa pode ser None
            recente = PastaRecente.registrar_acesso(user, pasta, empresa)

            return Response(PastaRecenteSerializer(recente).data)

        except Pasta.DoesNotExist:
            return Response({'error': 'Pasta não encontrada'}, status=404)


class DashboardPastasAPIView(APIView):
    """
    Retorna todas as pastas para o dashboard: fixadas, recentes e raiz
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        empresa_id = request.query_params.get('empresa_id')

        # Pastas fixadas
        if empresa_id:
            pastas_fixadas = PastaFixada.objects.filter(
                usuario=user,
                empresa_id=empresa_id
            ).select_related('pasta', 'empresa')
        else:
            pastas_fixadas = PastaFixada.objects.filter(
                usuario=user
            ).select_related('pasta', 'empresa')

        # Para cada pasta fixada, vamos calcular os valores individualmente
        for fixada in pastas_fixadas:
            if hasattr(fixada, 'pasta') and fixada.pasta:
                # Calcular tamanho e contagem individual
                fixada.pasta.individual_size = fixada.pasta.get_individual_size()
                fixada.pasta.individual_files_count = fixada.pasta.get_immediate_files_count()

        fixadas_serializer = PastaFixadaSerializer(pastas_fixadas, many=True)

        # Pastas recentes
        if empresa_id:
            pastas_recentes = PastaRecente.objects.filter(
                usuario=user,
                empresa_id=empresa_id
            ).select_related('pasta', 'empresa')
        else:
            pastas_recentes = PastaRecente.objects.filter(
                usuario=user
            ).select_related('pasta', 'empresa')

        # Para cada pasta recente, calcular os valores
        for recente in pastas_recentes:
            if hasattr(recente, 'pasta') and recente.pasta:
                recente.pasta.individual_size = recente.pasta.get_individual_size()
                recente.pasta.individual_files_count = recente.pasta.get_immediate_files_count()

        recentes_serializer = PastaRecenteSerializer(pastas_recentes, many=True)

        # Pastas raiz - usando annotate para otimizar
        # pastas_raiz = self._get_pastas_raiz(user, empresa_id)
        # raiz_serializer = PastaModelSerializer(pastas_raiz, many=True)

        return Response({
            'empresa_id': empresa_id,
            'fixadas': fixadas_serializer.data,
            'recentes': recentes_serializer.data,
            # 'raiz': raiz_serializer.data
        })

    def _get_pastas_raiz(self, user, empresa_id=None):
        """Replica a lógica de PastaListCreateAPIView com empresa_id opcional"""

        # Superusuário - comportamento padrão
        if user.is_superuser:
            if empresa_id:
                pastas_ids = AdministradorPasta.objects.filter(
                    empresa_id=empresa_id
                ).values_list('pasta_id', flat=True).distinct()

                return Pasta.objects.filter(
                    id__in=pastas_ids,
                    pasta_pai__isnull=True,
                    status='1'
                ).annotate(
                    individual_size=Sum('arquivos_da_pasta__tamanho', filter=Q(arquivos_da_pasta__status='1')),
                    individual_files_count=Count('arquivos_da_pasta', filter=Q(arquivos_da_pasta__status='1'))
                ).order_by('nome')
            else:
                # Sem empresa_id, retorna todas as pastas raiz
                return Pasta.objects.filter(
                    pasta_pai__isnull=True,
                    status='1'
                ).annotate(
                    individual_size=Sum('arquivos_da_pasta__tamanho', filter=Q(arquivos_da_pasta__status='1')),
                    individual_files_count=Count('arquivos_da_pasta', filter=Q(arquivos_da_pasta__status='1'))
                ).order_by('nome')

        # Usuário comum - comportamento padrão
        try:
            if empresa_id:
                # Com empresa_id especificada
                pastas_administradas = AdministradorPasta.objects.filter(
                    funcionario=user,
                    empresa_id=empresa_id
                )

                if pastas_administradas.exists():
                    # É administrador da empresa especificada
                    pastas_ids = pastas_administradas.values_list('pasta_id', flat=True)
                    return Pasta.objects.filter(
                        id__in=pastas_ids,
                        pasta_pai__isnull=True,
                        status='1'
                    ).annotate(
                        individual_size=Sum('arquivos_da_pasta__tamanho', filter=Q(arquivos_da_pasta__status='1')),
                        individual_files_count=Count('arquivos_da_pasta', filter=Q(arquivos_da_pasta__status='1'))
                    ).order_by('nome')
                else:
                    # Verifica se a empresa pertence ao usuário
                    if hasattr(user, 'empresa') and str(user.empresa.id) == empresa_id:
                        return Pasta.objects.filter(
                            clientes_da_pasta__empresa_id=empresa_id,
                            pasta_pai__isnull=True,
                            status='1'
                        ).annotate(
                            individual_size=Sum('arquivos_da_pasta__tamanho', filter=Q(arquivos_da_pasta__status='1')),
                            individual_files_count=Count('arquivos_da_pasta', filter=Q(arquivos_da_pasta__status='1'))
                        ).distinct().order_by('nome')
                    else:
                        # Usuário não tem permissão para acessar pastas desta empresa
                        return Pasta.objects.none()
            else:
                # Sem empresa_id - comportamento padrão
                pastas_administradas = AdministradorPasta.objects.filter(funcionario=user)

                if pastas_administradas.exists():
                    # Retorna todas as pastas que administra
                    pastas_ids = pastas_administradas.values_list('pasta_id', flat=True)
                    return Pasta.objects.filter(
                        id__in=pastas_ids,
                        pasta_pai__isnull=True,
                        status='1'
                    ).annotate(
                        individual_size=Sum('arquivos_da_pasta__tamanho', filter=Q(arquivos_da_pasta__status='1')),
                        individual_files_count=Count('arquivos_da_pasta', filter=Q(arquivos_da_pasta__status='1'))
                    ).order_by('nome')
                else:
                    # Retorna pastas da empresa do usuário
                    if hasattr(user, 'empresa'):
                        return Pasta.objects.filter(
                            clientes_da_pasta__empresa=user.empresa,
                            pasta_pai__isnull=True,
                            status='1'
                        ).annotate(
                            individual_size=Sum('arquivos_da_pasta__tamanho', filter=Q(arquivos_da_pasta__status='1')),
                            individual_files_count=Count('arquivos_da_pasta', filter=Q(arquivos_da_pasta__status='1'))
                        ).distinct().order_by('nome')
                    else:
                        return Pasta.objects.none()

        except Exception as e:
            print(f"Erro ao buscar pastas: {e}")
            return Pasta.objects.none()
