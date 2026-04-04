import csv
import json
import chardet
import os

from django.http import HttpResponse
from django.utils import timezone
from django.http import FileResponse, Http404

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# Serializers, Models
from leads_api.models import Company, Product, Event, Lead, Cnes, Municipalities
from leads_api.serializer import (
    CompanySerializer, ProductSerializer, EventSerializer,
    LeadSerializer, FileUploadSerializer,
    CnesFileUploadSerializer, CnesSerializer,
    MunicipalitiesSerializer, MunicipalitiesFileUploadSerializer
)

from .services.gemini import GeminiService
from .services.duplication import DuplicationService

# Filters
from app.utils import utils
from django_filters.rest_framework import DjangoFilterBackend
from .filters import LeadsFilter, CnesFilter, MunicipalitiesFilter

from .services.import_service import ImportService
from rest_framework.parsers import MultiPartParser, FormParser
from decimal import Decimal, InvalidOperation

from django.db import transaction

from celery.result import AsyncResult
from celery import current_app
from django.core.cache import cache


class CompanyListCreateView(generics.ListCreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]

    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        paginate = self.request.query_params.get("paginate", "true")

        if paginate.lower() in ["false", "0", "no"]:
            return None  # desativa paginação somente se pedir explicitamente

        return super().paginate_queryset(queryset)


class CompanyRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]


class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        paginate = self.request.query_params.get("paginate", "true")

        if paginate.lower() in ["false", "0", "no"]:
            return None  # desativa paginação somente se pedir explicitamente

        return super().paginate_queryset(queryset)


class ProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]


class EventListCreateView(generics.ListCreateAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]


class EventRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]


class EventGenerateEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = generics.get_object_or_404(Event, pk=pk)
        result = GeminiService.generate_event_followup(
            event.nome,
            str(event.data)
        )

        if result:
            return Response(result)

        return Response(
            {"error": "Falha na geração de IA"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class LeadListCreateView(generics.ListCreateAPIView):
    queryset = Lead.objects.filter(deleted_at__isnull=True).order_by('-created_at')
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = LeadsFilter
    pagination_class = utils.CustomPageSizePagination

    def get_filterset_kwargs(self):
        """
        Interfere nos argumentos do filtro para normalizar
        os parâmetros da URL para minúsculo.
        """
        kwargs = super().get_filterset_kwargs()

        if kwargs.get('data'):
            # Cria uma cópia mutável dos parâmetros da URL
            clean_data = kwargs['data'].copy()

            for key, value in clean_data.items():
                # Normaliza apenas campos de texto (evita mexer em IDs ou números)
                if isinstance(value, str):
                    clean_data[key] = value.lower()

            kwargs['data'] = clean_data

        return kwargs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class LeadRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    # Garante que não acessa leads deletados via ID
    queryset = Lead.objects.filter(deleted_at__isnull=True)
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        # Soft Delete: Marca a data de exclusão e o usuário que deletou
        request = self.request
        user = request.user if request and hasattr(request, 'user') else None

        # Soft delete em todos os contatos relacionados
        for contato in instance.contatos.all():
            contato.deleted_at = timezone.now()
            if user and user.is_authenticated:
                contato.deleted_by = user
            contato.save()

        # Soft delete no Lead
        instance.deleted_at = timezone.now()
        if user and user.is_authenticated:
            instance.deleted_by = user
        instance.save()


class LeadExportView(generics.GenericAPIView):
    """
    Exportação COMPLETA (Dump) de todos os leads ativos.
    Utiliza prefetch_related para otimizar as consultas de ManyToMany e Reverse FK.
    """
    # Otimizamos a query com prefetch_related para 'empresas_grupo', 'produtos_interesse' e 'contatos'
    queryset = Lead.objects.filter(deleted_at__isnull=True)\
        .prefetch_related('empresas_grupo', 'produtos_interesse', 'contatos')\
        .order_by('-created_at')

    filter_backends = []
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get(self, request, *args, **kwargs):
        leads_to_export = self.get_queryset()

        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="leads_full_export.csv"'},
        )
        response.write('\ufeff')  # BOM para UTF-8 no Excel

        writer = csv.writer(response, delimiter=';')

        # Cabeçalho baseado estritamente no model Lead
        writer.writerow([
            'Empresa', 'Apelido', 'CNPJ', 'CNES', 'Telefone', 'Cidade', 'Estado',
            'Segmento', 'Classificação', 'Origem', 'Cod. Nat. Jurídica',
            'Natureza Jurídica', 'Empresas do Grupo', 'Produtos Interesse', 
            'Contatos (JSON)', 'Observações', 'Criado em', 'Atualizado em'
        ])

        for lead in leads_to_export:
            # Extração de nomes das relações ManyToMany
            grupos = ", ".join([g.nome for g in lead.empresas_grupo.all()])
            produtos = ", ".join([p.nome for p in lead.produtos_interesse.all()])

            # Montagem da lista de contatos (RelatedName definido no model de Contatos costuma ser 'contatos')
            contatos_list = [
                {
                    "nome": c.nome,
                    "setor": c.setor,
                    "email": c.email,
                    "email_extra": c.email_extra,
                    "celular": c.celular
                }
                for c in lead.contatos.all()
            ]

            writer.writerow([
                lead.empresa,
                lead.apelido or "",
                lead.cnpj or "",
                lead.cnes or "",
                lead.telefone or "",
                lead.cidade or "",
                lead.estado or "",
                lead.segmento or "",
                lead.classificacao or "Não Cliente",
                lead.origem or "",
                lead.cod_nat_jur or "",
                lead.natureza_juridica or "",
                grupos,
                produtos,
                json.dumps(contatos_list, ensure_ascii=False),
                lead.observacoes or "",
                lead.created_at.strftime('%d/%m/%Y %H:%M') if lead.created_at else "",
                lead.updated_at.strftime('%d/%m/%Y %H:%M') if lead.updated_at else ""
            ])

        return response


class LeadCheckDuplicityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = DuplicationService.analyze(request.data)
        return Response(result)


class LeadGenerateStrategyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = GeminiService.generate_sales_strategy(request.data)
        if result:
            return Response(result)

        return Response(
            {"error": "Falha na geração de IA"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class LeadBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids', [])

        if not ids:
            return Response(
                {"error": "No IDs provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filtra apenas leads que ainda não foram deletados
        leads_qs = Lead.objects.filter(id__in=ids, deleted_at__isnull=True)
        leads_count = leads_qs.count()

        # Executa Soft Delete em massa
        leads_qs.update(deleted_at=timezone.now())

        return Response({
            "status": "deleted",
            "requested_ids": ids,
            "leads_deleted": leads_count
        })


class LeadLastTimestampsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        last_lead = Lead.objects.filter(deleted_at__isnull=True).order_by('-created_at').first()

        if not last_lead:
            return Response({
                "created_at": None,
                "updated_at": None
            })

        return Response({
            "id": last_lead.id,
            "created_at": last_lead.created_at,
            "updated_at": last_lead.updated_at
        })


class LeadImportStatusView(APIView):
    """
    Consulta status de uma task de importação
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task = AsyncResult(task_id)

        result = {
            "task_id": task_id,
            "status": task.status,
            "ready": task.ready(),
            "successful": task.successful() if task.ready() else None,
            "failed": task.failed() if task.ready() else None,
        }

        if task.ready():
            if task.successful():
                result["result"] = task.result
            else:
                result["error"] = str(task.info)
        else:
            # Se não estiver pronto, tenta pegar do cache
            cached_result = cache.get(f'import_result_{task_id}')
            if cached_result:
                result["partial_result"] = cached_result

        return Response(result)


class LeadImportCancelView(APIView):
    """
    Cancela uma task de importação em andamento
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        try:
            task = AsyncResult(task_id)

            # Verifica se a task ainda está pendente ou em progresso
            if task.state in ['PENDING', 'STARTED', 'RETRY']:
                # Revoga a task
                current_app.control.revoke(task_id, terminate=True, signal='SIGKILL')

                # Aguarda um momento para o worker processar o cancelamento
                import time
                time.sleep(0.5)

                # Remove do cache
                cache.delete(f'import_result_{task_id}')
                cache.delete(f'import_task_created_{task_id}')

                # Remove da lista de tasks do usuário
                user_task_key = f'user_import_tasks_{request.user.id}'
                task_ids = cache.get(user_task_key, [])
                if task_id in task_ids:
                    task_ids.remove(task_id)
                    cache.set(user_task_key, task_ids, timeout=86400)

                return Response({
                    "message": f"Task {task_id} cancelada com sucesso",
                    "task_id": task_id,
                    "previous_state": task.state
                })
            else:
                return Response({
                    "message": f"Task {task_id} não pode ser cancelada (estado: {task.state})",
                    "task_id": task_id,
                    "state": task.state
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": f"Erro ao cancelar task: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class LeadImportTasksView(APIView):
    """
    Lista tasks de importação do usuário atual
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Pega os parâmetros de filtro
        status_filter = request.query_params.get('status', None)
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))

        # Pega as tasks do cache (implementar conforme necessidade)
        # Aqui você pode armazenar os task_ids em uma lista no cache do usuário
        user_task_key = f'user_import_tasks_{request.user.id}'
        task_ids = cache.get(user_task_key, [])

        # Limita e pagina
        task_ids = task_ids[offset:offset + limit]

        tasks = []
        for task_id in task_ids:
            task = AsyncResult(task_id)
            tasks.append({
                "task_id": task_id,
                "status": task.status,
                "ready": task.ready(),
                "created_at": cache.get(f'import_task_created_{task_id}')
            })

        # Filtra por status se necessário
        if status_filter:
            tasks = [t for t in tasks if t['status'] == status_filter]

        return Response({
            "tasks": tasks,
            "total": len(task_ids),
            "limit": limit,
            "offset": offset
        })


class LeadImportDownloadReportView(APIView):
    """
    Download do relatório de erros gerado durante a importação
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        report_path = request.data.get('report_path')

        if not report_path:
            return Response(
                {"error": "report_path é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Garante que o caminho está dentro do diretório reports (segurança)
        if '..' in report_path or not report_path.startswith('reports/'):
            return Response(
                {"error": "Caminho de arquivo inválido"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica se o arquivo existe
        if not os.path.exists(report_path):
            return Response(
                {"error": f"Relatório não encontrado: {report_path}"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Abre o arquivo para download
            file_handle = open(report_path, 'rb')
            response = FileResponse(
                file_handle,
                content_type='text/plain; charset=utf-8',
                as_attachment=True,
                filename=os.path.basename(report_path)
            )
            # Adiciona cabeçalhos para garantir o download
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(report_path)}"'
            response['Content-Type'] = 'text/plain; charset=utf-8'
            return response
        except Exception as e:
            return Response(
                {"error": f"Erro ao baixar relatório: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeadImportCleanupView(APIView):
    """
    Limpa tasks antigas e arquivos de relatório
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        # Limpa tasks do usuário
        user_task_key = f'user_import_tasks_{request.user.id}'
        old_tasks = cache.get(user_task_key, [])

        cleaned_tasks = []
        for task_id in old_tasks:
            task = AsyncResult(task_id)
            # Mantém apenas tasks recentes (últimas 24h) que ainda estão ativas
            created_at = cache.get(f'import_task_created_{task_id}')
            if created_at:
                from datetime import datetime
                created_time = datetime.fromisoformat(created_at)
                if (datetime.now() - created_time).days < 1 and task.state in ['PENDING', 'PROGRESS']:
                    cleaned_tasks.append(task_id)

        cache.set(user_task_key, cleaned_tasks, timeout=86400)

        # Opcional: Limpar arquivos de relatório antigos
        import os
        import glob
        from datetime import datetime, timedelta

        reports_dir = 'reports/'
        if os.path.exists(reports_dir):
            for filepath in glob.glob(os.path.join(reports_dir, '*.txt')):
                # Remove arquivos com mais de 7 dias
                if os.path.getctime(filepath) < (datetime.now() - timedelta(days=7)).timestamp():
                    try:
                        os.remove(filepath)
                    except:
                        pass

        return Response({
            "message": "Limpeza concluída",
            "tasks_removed": len(old_tasks) - len(cleaned_tasks),
            "remaining_tasks": len(cleaned_tasks)
        })


class LeadImportView(APIView):
    """
    ### Comandos Básicos:

        # Iniciar Celery Worker (Windows)
        celery -A app worker --loglevel=info --pool=solo
        celery -A app worker --loglevel=info --pool=threads

        # Iniciar Celery Worker (Linux/Mac)
        celery -A app worker --loglevel=info

        # Iniciar com mais workers
        celery -A app worker --loglevel=info --concurrency=4

        # Iniciar Celery Beat (para tarefas agendadas)
        celery -A app beat --loglevel=info

        # Iniciar Flower (monitoramento) - precisa instalar: pip install flower
        celery -A app flower --port=5555
        # Acessar: http://localhost:5555

    ### Comandos de Status e Inspeção:

        # Ver status do worker
        celery -A app status

        # Ver workers ativos
        celery -A app inspect active

        # Ver tasks registradas
        celery -A app inspect registered

        # Ver estatísticas
        celery -A app inspect stats

        # Ver tarefas em andamento
        celery -A app inspect active

        # Ver tarefas agendadas
        celery -A app inspect scheduled

        # Ver tarefas reservadas
        celery -A app inspect reserved

    ### Comandos de Controle:

        # Parar worker (graceful)
        celery -A app control shutdown

        # Limpar todas as tasks (purge)
        celery -A app purge

        # Revogar uma task específica
        celery -A app control revoke <task_id>

        # Revogar e terminar (force)
        celery -A app control revoke <task_id> --terminate

        # Revogar todas as tasks em uma fila
        celery -A app control revoke --all

        # Pausar um worker
        celery -A app control pause

        # Retomar um worker
        celery -A app control resume

        # Rate limit
        celery -A app control rate_limit tasks.add 10/s

    ### Comandos de Debug:

        # Rodar task de debug
        celery -A app call leads_api.tasks.import_leads_csv_task --args='["file_content", "test.xlsx", false, "xlsx"]'

        # Ver logs detalhados
        celery -A app worker --loglevel=debug

        # Ver logs em arquivo
        celery -A app worker --loglevel=info --logfile=celery.log

        # Com saída colorida (Linux/Mac)
        celery -A app worker --loglevel=info --color
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET para documentação (opcional)
        """
        return Response({
            "message": "Use POST para enviar arquivo CSV",
            "required_fields": ["Nome da conta", "CNPJ"],
            "optional_fields": ["CNES", "Primeiro Nome", "Sobrenome", "Email", "Celular"],
            "example": "POST /api/v1/leads/import/?celery=true"
        })

    def post(self, request, *args, **kwargs):
        serializer = FileUploadSerializer(data=request.data)
        if serializer.is_valid():
            file = serializer.validated_data['file']

            # Verifica se deve usar Celery (pode vir do query param)
            use_celery = request.query_params.get('celery', 'true').lower() == 'true'

            # Opção para forçar processamento síncrono (útil para testes)
            force_sync = request.query_params.get('sync', 'false').lower() == 'true'
            if force_sync:
                use_celery = False

            try:
                result = ImportService.process_csv(file, False, celery=use_celery)

                # Se usou Celery, registra o task_id para o usuário
                if use_celery and 'task_id' in result:
                    user_task_key = f'user_import_tasks_{request.user.id}'
                    task_ids = cache.get(user_task_key, [])
                    task_ids.insert(0, result['task_id'])  # Adiciona no início
                    # Mantém apenas os últimos 100 tasks
                    task_ids = task_ids[:100]
                    cache.set(user_task_key, task_ids, timeout=86400)  # 24 horas

                    # Salva timestamp de criação
                    from datetime import datetime
                    cache.set(f'import_task_created_{result["task_id"]}', datetime.now().isoformat(), timeout=86400)

                return Response(result, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CnesListView(generics.ListAPIView):
    # permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = CnesFilter
    queryset = Cnes.objects.all().order_by('id')
    serializer_class = CnesSerializer
    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        paginate = self.request.query_params.get("paginate", "true")

        if paginate.lower() in ["false", "0", "no"]:
            return None  # desativa paginação somente se pedir explicitamente

        return super().paginate_queryset(queryset)


class CnesImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def parse_decimal(self, value):
        """
        pip install chardet

        Trata decimal com:
        - 1.234,56
        - 1234.56
        - vazio
        """
        if not value:
            return Decimal("0.00")

        value = value.strip()

        # Se vier formato brasileiro 1.234,56
        if "," in value and "." in value:
            value = value.replace(".", "").replace(",", ".")
        elif "," in value:
            value = value.replace(",", ".")

        try:
            return Decimal(value)
        except InvalidOperation:
            return Decimal("0.00")

    def parse_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def post(self, request, *args, **kwargs):
        serializer = CnesFileUploadSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file = serializer.validated_data['file']

        # ==========================
        # Detectar encoding automaticamente
        # ==========================
        raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result.get("encoding") or "utf-8"

        try:
            decoded_file = raw_data.decode(encoding)
        except UnicodeDecodeError:
            decoded_file = raw_data.decode("latin1")

        reader = csv.DictReader(decoded_file.splitlines(), delimiter=';')

        batch = []
        BATCH_SIZE = 5000
        total_imported = 0

        try:
            with transaction.atomic():
                for row in reader:

                    # Ignora linha totalmente vazia
                    if not any(row.values()):
                        continue

                    batch.append(
                        Cnes(
                            razao_social=row.get('razao_social', '').strip(),
                            fantasia=row.get('fantasia', '').strip(),
                            cod_nat_jur=row.get('cod_nat_jur', '').strip(),
                            natureza_juridica=row.get('natureza_juridica', '').strip(),
                            cnes=row.get('cnes', '').strip(),
                            cpf_cnpj=row.get('cpf_cnpj', '').strip(),
                            tipo_unidade=row.get('tipo_unidade', '').strip(),
                            endereco=row.get('endereco') or None,
                            cidade=row.get('cidade', '').strip(),
                            uf=row.get('uf', '').strip(),
                            telefone=row.get('telefone') or None,
                            faturamento_sus_2020=self.parse_decimal(
                                row.get('faturamento_sus_2020')
                            ),
                            qtde_leitos=self.parse_int(
                                row.get('qtde_leitos')
                            ),
                            file=file.name
                        )
                    )

                    if len(batch) >= BATCH_SIZE:
                        Cnes.objects.bulk_create(batch, batch_size=BATCH_SIZE)
                        total_imported += len(batch)
                        batch = []

                # Inserir restante
                if batch:
                    Cnes.objects.bulk_create(batch, batch_size=BATCH_SIZE)
                    total_imported += len(batch)

            return Response({
                "status": "success",
                "encoding_detected": encoding,
                "imported": total_imported
            })

        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )


class MunicipalitiesView(generics.ListAPIView):
    # permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = MunicipalitiesFilter
    queryset = Municipalities.objects.all().order_by('id')
    serializer_class = MunicipalitiesSerializer
    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        paginate = self.request.query_params.get("paginate", "true")

        if paginate.lower() in ["false", "0", "no"]:
            return None  # desativa paginação somente se pedir explicitamente

        return super().paginate_queryset(queryset)


class MunicipalitiesImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = MunicipalitiesFileUploadSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file = serializer.validated_data['file']

        # Detectar encoding
        raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result.get("encoding") or "utf-8"

        try:
            decoded_file = raw_data.decode(encoding)
        except UnicodeDecodeError:
            decoded_file = raw_data.decode("latin1")

        reader = csv.DictReader(decoded_file.splitlines(), delimiter=';')

        batch = []
        BATCH_SIZE = 5000
        total_imported = 0

        try:
            with transaction.atomic():
                for row in reader:

                    if not any(row.values()):
                        continue

                    batch.append(
                        Municipalities(
                            co_municip=row.get('co_municip', '').replace('"', '').strip(),
                            ds_nome=row.get('ds_nome', '').replace('"', '').strip(),
                            ds_nomepad=row.get('ds_nomepad', '').replace('"', '').strip(),
                            co_uf=row.get('co_uf', '').replace('"', '').strip(),
                        )
                    )

                    if len(batch) >= BATCH_SIZE:
                        Municipalities.objects.bulk_create(
                            batch,
                            batch_size=BATCH_SIZE,
                            ignore_conflicts=True  # evita erro se já existir
                        )
                        total_imported += len(batch)
                        batch = []

                if batch:
                    Municipalities.objects.bulk_create(
                        batch,
                        batch_size=BATCH_SIZE,
                        ignore_conflicts=True
                    )
                    total_imported += len(batch)

            return Response({
                "status": "success",
                "encoding_detected": encoding,
                "imported": total_imported
            })

        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
