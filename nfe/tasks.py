import logging
import os
from re import sub
from lxml import etree

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from pynfe.processamento.comunicacao import ComunicacaoSefaz
from pynfe.utils.flags import NAMESPACE_NFE
from pynfe.utils.descompactar import DescompactaGzip

from empresa.models import Empresa, HistoricoNSU
from nfe.processor.nfe_processor import NFeProcessor
from nfe_resumo.processor.resumo_processor import ResumoNFeProcessor
from nfe_evento.processor.evento_processor import EventoNFeProcessor

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='nfe.tasks.automatizar_nfe', max_retries=3, default_retry_delay=60)
def automatizar_nfe_task(self):
    """
    Task Celery para consultar documentos NFe via SEFAZ
    """
    task_id = self.request.id
    logger.info(f"[TASK {task_id}] Iniciando automação NFe...")

    ns = {'ns': NAMESPACE_NFE}
    xml_dir = os.path.join(settings.MEDIA_ROOT, 'xml')
    os.makedirs(xml_dir, exist_ok=True)

    # FILTRAR APENAS EMPRESAS COM CERTIFICADO (file preenchido)
    empresas_com_certificado = Empresa.objects.filter(file__isnull=False).exclude(file='')

    if not empresas_com_certificado.exists():
        logger.info("[TASK] Nenhuma empresa com certificado encontrada.")
        return {"status": "success", "message": "Nenhuma empresa com certificado"}

    logger.info(f"[TASK] Processando {empresas_com_certificado.count()} empresa(s) com certificado.")

    results = {
        "total_empresas": empresas_com_certificado.count(),
        "empresas_processadas": 0,
        "empresas_com_erro": 0,
        "documentos_processados": 0,
        "nsu_atualizados": 0,
        "detalhes": []
    }

    for empresa in empresas_com_certificado:
        empresa_result = {
            "empresa": empresa.razao_social,
            "cnpj": empresa.documento,
            "status": "processando",
            "documentos": 0,
            "erros": []
        }

        logger.info(f"[TASK] Processando empresa: {empresa.razao_social}")

        cert_path = empresa.file.path
        if not os.path.isfile(cert_path):
            logger.error(f"[TASK] Certificado não encontrado: {cert_path}")
            empresa_result["status"] = "erro"
            empresa_result["erros"].append(f"Certificado não encontrado: {cert_path}")
            results["empresas_com_erro"] += 1
            results["detalhes"].append(empresa_result)
            continue

        try:
            # Pega último NSU do banco ou usa 0 se não houver
            try:
                ultimo_nsu = empresa.historico_empresa.order_by('-created_at').first()
                nsu_para_consulta = int(ultimo_nsu.nsu) if ultimo_nsu else 0
            except Exception as e:
                logger.warning(f"[TASK] Erro ao buscar NSU anterior: {e}")
                nsu_para_consulta = 0

            logger.info(f"[TASK] Consultando SEFAZ para NSU: {nsu_para_consulta}")

            con = ComunicacaoSefaz(empresa.uf, cert_path, empresa.senha, homologacao=False)

            response = con.consulta_distribuicao(
                cnpj=sub(r'\D', '', empresa.documento),
                chave='',
                nsu=nsu_para_consulta,
                consulta_nsu_especifico=False
            )

            if not response or not response.text.startswith('<'):
                logger.error(f"[TASK] Resposta inválida para {empresa.razao_social}")
                empresa_result["status"] = "erro"
                empresa_result["erros"].append("Resposta inválida da SEFAZ")
                results["empresas_com_erro"] += 1
                results["detalhes"].append(empresa_result)
                continue

            xml = response.text
            resposta = etree.fromstring(xml.encode('utf-8'))

            cStat = resposta.xpath('//ns:retDistDFeInt/ns:cStat', namespaces=ns)[0].text
            xMotivo = resposta.xpath('//ns:retDistDFeInt/ns:xMotivo', namespaces=ns)[0].text
            logger.info(f"[TASK] {empresa.razao_social} - cStat: {cStat} | xMotivo: {xMotivo}")

            if cStat in ('137', '656'):
                logger.info(f"[TASK] Nada a processar para {empresa.razao_social}")
                empresa_result["status"] = "sucesso"
                empresa_result["mensagem"] = f"Nada a processar (cStat {cStat})"
                results["empresas_processadas"] += 1
                results["detalhes"].append(empresa_result)

                # Atualiza NSU mesmo sem documentos
                if cStat == "138":
                    max_nsu_nodes = resposta.xpath('//ns:retDistDFeInt/ns:maxNSU', namespaces=ns)
                    if max_nsu_nodes:
                        novo_nsu = int(max_nsu_nodes[0].text)
                        HistoricoNSU.objects.create(empresa=empresa, nsu=novo_nsu)
                        results["nsu_atualizados"] += 1
                        logger.info(f"[TASK] NSU atualizado para {empresa.razao_social}: {novo_nsu}")

                continue

            documentos = resposta.xpath('//ns:retDistDFeInt/ns:loteDistDFeInt/ns:docZip', namespaces=ns)
            logger.info(f"[TASK] Encontrados {len(documentos)} documento(s) para processar.")
            empresa_result["documentos"] = len(documentos)

            for doc in documentos:
                tipo_schema = doc.attrib.get('schema')
                numero_nsu = doc.attrib.get('NSU')
                conteudo_zipado = doc.text

                # Descompacta o conteúdo do arquivo ZIP
                xml_descompactado = DescompactaGzip.descompacta(conteudo_zipado)
                conteudo = etree.tostring(xml_descompactado, encoding='utf-8').decode('utf-8')

                # Define o nome do arquivo dependendo do tipo de schema
                if tipo_schema == 'procNFe_v4.00.xsd':
                    filename = f'nfe_nsu-{numero_nsu}.xml'
                    tipo_documento = "nfe_nsu"
                elif tipo_schema == 'resNFe_v1.01.xsd':
                    filename = f'resumo_nsu-{numero_nsu}.xml'
                    tipo_documento = "resumo_nsu"
                else:
                    filename = f'outro_nsu-{numero_nsu}.xml'
                    tipo_documento = "outro_nsu"

                # Caminho absoluto para salvar o arquivo
                filepath = os.path.join(xml_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(conteudo)

                # Caminho relativo para enviar à API
                relative_path = os.path.join('xml', filename)
                logger.info(f"[TASK] Documento {numero_nsu} salvo em {relative_path}")

                try:
                    if tipo_documento == "nfe_nsu":
                        processor = NFeProcessor(empresa, numero_nsu, relative_path)
                        processor.processar(debug=False)
                        results["documentos_processados"] += 1
                        logger.info(f"[TASK] Documento {numero_nsu} processado")

                    elif tipo_documento == "resumo_nsu":
                        processor = ResumoNFeProcessor(empresa, numero_nsu, relative_path)
                        processor.processar()
                        results["documentos_processados"] += 1
                        logger.info(f"[TASK] Resumo {numero_nsu} processado")
                    else:
                        processor = EventoNFeProcessor(empresa, numero_nsu, relative_path)
                        processor.processar()
                        results["documentos_processados"] += 1
                        logger.info(f"[TASK] Evento {numero_nsu} processado")

                except Exception as e:
                    logger.error(f"[TASK] Falha ao processar documento {numero_nsu}: {str(e)}")
                    empresa_result["erros"].append(f"Documento {numero_nsu}: {str(e)}")

            # Atualiza NSU no banco somente se resposta for válida
            if cStat == "138":
                max_nsu_nodes = resposta.xpath('//ns:retDistDFeInt/ns:maxNSU', namespaces=ns)
                if max_nsu_nodes:
                    novo_nsu = int(max_nsu_nodes[0].text)
                    HistoricoNSU.objects.create(empresa=empresa, nsu=novo_nsu)
                    results["nsu_atualizados"] += 1
                    logger.info(f"[TASK] NSU atualizado para {empresa.razao_social}: {novo_nsu}")

            empresa_result["status"] = "sucesso"
            results["empresas_processadas"] += 1

        except Exception as e:
            logger.error(f"[TASK] Falha ao processar {empresa.razao_social}: {str(e)}", exc_info=True)
            empresa_result["status"] = "erro"
            empresa_result["erros"].append(str(e))
            results["empresas_com_erro"] += 1

        results["detalhes"].append(empresa_result)

    logger.info(f"[TASK] Automação concluída: {results}")

    # Salva resultado no cache para consulta
    cache.set(f'automatizacao_nfe_result_{task_id}', results, timeout=3600)

    return results


@shared_task(name='nfe.tasks.automatizar_nfe_empresa_especifica')
def automatizar_nfe_empresa_task(empresa_id):
    """
    Task para processar uma empresa específica (útil para debugging)
    """
    try:
        Empresa.objects.get(id=empresa_id, file__isnull=False)
    except Empresa.DoesNotExist:
        return {"error": f"Empresa {empresa_id} não encontrada ou sem certificado"}

    # Reutiliza a lógica principal para uma empresa
    from nfe.management.commands.automatizando import Command
    Command()

    # Aqui você pode adaptar para processar apenas uma empresa
    # Por simplicidade, vamos chamar a task principal
    return automatizar_nfe_task.delay()
