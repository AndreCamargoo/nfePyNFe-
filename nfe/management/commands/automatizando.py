import os
import requests
import time  # Importar o módulo time
from re import sub
from lxml import etree

from django.core.management.base import BaseCommand
from django.conf import settings

from pynfe.processamento.comunicacao import ComunicacaoSefaz
from pynfe.utils.flags import NAMESPACE_NFE
from pynfe.utils.descompactar import DescompactaGzip

from empresa.models import Empresa, HistoricoNSU


class Command(BaseCommand):
    help = 'Consulta documentos NFe via SEFAZ, salva XML em media/xml/, envia para API e atualiza o NSU no banco.'

    def obter_token(self):
        login_url = f"{settings.API_URL}/authentication/token/"
        login_data = {
            "username": settings.API_USERNAME,
            "password": settings.API_PASSWORD
        }

        try:
            response = requests.post(login_url, json=login_data)
            response.raise_for_status()
            return response.json().get("access")
        except requests.RequestException as e:
            raise RuntimeError(f"[ERRO] Não foi possível autenticar: {e}")

    def handle(self, *args, **options):
        while True:  # Loop infinito
            try:
                ns = {'ns': NAMESPACE_NFE}
                xml_dir = os.path.join(settings.MEDIA_ROOT, 'xml')
                os.makedirs(xml_dir, exist_ok=True)

                token = self.obter_token()
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                }

                for empresa in Empresa.objects.all():
                    cert_path = empresa.file.path
                    if not os.path.isfile(cert_path):
                        self.stderr.write(f'[ERRO] Certificado não encontrado: {cert_path}')
                        continue
                    else:
                        self.stdout.write(f'[OK] Certificado encontrado: {cert_path}')

                    try:
                        # Pega último NSU do banco ou usa 0 se não houver
                        try:
                            ultimo_nsu = empresa.historico_empresa.order_by('-created_at').first()
                            nsu_para_consulta = int(ultimo_nsu.nsu) if ultimo_nsu else 0
                        except Exception as e:
                            self.stderr.write(f'[WARN] Erro ao buscar NSU anterior: {e}')
                            nsu_para_consulta = 0

                        con = ComunicacaoSefaz(empresa.uf, cert_path, empresa.senha, homologacao=False)
                        self.stdout.write(f"XML enviado: {con.ultimo_xml_enviado.decode('utf-8') if hasattr(con, 'ultimo_xml_enviado') else 'Sem XML disponível'}")

                        response = con.consulta_distribuicao(
                            cnpj=sub(r'\D', '', empresa.documento),
                            chave='',
                            nsu=nsu_para_consulta,
                            consulta_nsu_especifico=False
                        )

                        if not response or not response.text.startswith('<'):
                            self.stderr.write(f'[ERRO] Resposta inválida para {empresa.razao_social}')
                            print(f"Resposta completa:\n{response.text}")
                            continue

                        xml = response.text
                        resposta = etree.fromstring(xml.encode('utf-8'))

                        cStat = resposta.xpath('//ns:retDistDFeInt/ns:cStat', namespaces=ns)[0].text
                        xMotivo = resposta.xpath('//ns:retDistDFeInt/ns:xMotivo', namespaces=ns)[0].text
                        self.stdout.write(f'{empresa.razao_social} - cStat: {cStat} | xMotivo: {xMotivo}')

                        if cStat in ('137', '656'):
                            self.stdout.write(f'[INFO] Nada a processar para {empresa.razao_social} (cStat {cStat})')
                            continue

                        documentos = resposta.xpath('//ns:retDistDFeInt/ns:loteDistDFeInt/ns:docZip', namespaces=ns)
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
                                tipo_documento = "nfe_nsu"  # Definido dinamicamente
                                router = "nfe"
                            elif tipo_schema == 'resNFe_v1.01.xsd':
                                filename = f'resumo_nsu-{numero_nsu}.xml'
                                tipo_documento = "resumo_nsu"  # Definido dinamicamente
                                router = "resumo"
                            else:
                                filename = f'outro_nsu-{numero_nsu}.xml'
                                tipo_documento = "outro_nsu"  # Definido dinamicamente
                                router = "nfes/evento/"

                            # Caminho absoluto para salvar o arquivo
                            filepath = os.path.join(xml_dir, filename)
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(conteudo)

                            # Caminho relativo para enviar à API
                            relative_path = os.path.join('xml', filename)
                            self.stdout.write(f'[SALVO] Documento {numero_nsu} salvo em {relative_path}')

                            try:
                                data = {
                                    "empresa_id": empresa.id,
                                    "nsu": numero_nsu,
                                    "fileXml": relative_path,  # Caminho relativo do arquivo XML
                                    "tipo": tipo_documento,  # Tipo de documento dinamicamente atribuído
                                }
                                api_url = f"{settings.API_URL}/{router}/"
                                api_response = requests.post(api_url, json=data, headers=headers)

                                if api_response.status_code == 200:
                                    self.stdout.write(f'[OK] Documento {numero_nsu} enviado e processado com sucesso.')
                                else:
                                    self.stderr.write(f'[ERRO] API respondeu com status {api_response.status_code}: {api_response.text}')

                            except Exception as api_error:
                                self.stderr.write(f'[ERRO] Falha ao enviar para API: {api_error}')

                        # Atualiza NSU no banco somente se resposta for válida
                        if cStat == "138":
                            max_nsu_nodes = resposta.xpath('//ns:retDistDFeInt/ns:maxNSU', namespaces=ns)
                            if max_nsu_nodes:
                                novo_nsu = int(max_nsu_nodes[0].text)
                                HistoricoNSU.objects.create(empresa=empresa, nsu=novo_nsu)
                                self.stdout.write(f'[OK] NSU atualizado para {empresa.razao_social}: {novo_nsu}')

                    except Exception as e:
                        self.stderr.write(f'[ERRO] Falha ao processar {empresa.razao_social}: {str(e)}')

                # Aguarda 1 hora (3600 segundos) antes da próxima execução
                self.stdout.write('[INFO] Aguardando 1 hora para próxima consulta...')
                time.sleep(3600)

            except Exception as global_error:
                self.stderr.write(f'[ERRO GLOBAL] Erro inesperado: {global_error}')
                self.stdout.write('[INFO] Aguardando 1 hora para tentar novamente...')
                time.sleep(3600)
