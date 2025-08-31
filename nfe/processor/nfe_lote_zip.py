import os
import token
import zipfile
import tempfile

from django.conf import settings
import requests

from nfe.processor.nfe_processor import NFeProcessor
from nfe_evento.processor.evento_processor import EventoNFeProcessor
from nfe_resumo.processor.resumo_processor import ResumoNFeProcessor

from lxml import etree


class NFeLoteProcessor:
    def __init__(self, empresa, nsu, arquivo_zip):
        self.empresa = empresa
        self.nsu = nsu
        self.arquivo_zip = arquivo_zip

    def processar_zip(self):
        """Processa o arquivo ZIP e extrai os XMLs"""
        resultados = {
            'nfe_processadas': 0,
            'eventos_processados': 0,
            'resumos_processados': 0,
            'erros': []
        }

        # Criar diretório temporário
        with tempfile.TemporaryDirectory() as temp_dir:
            # Salvar o arquivo ZIP temporariamente
            zip_path = os.path.join(temp_dir, 'lote_nfe.zip')

            with open(zip_path, 'wb') as f:
                for chunk in self.arquivo_zip.chunks():
                    f.write(chunk)

            # Extrair arquivos do ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

                # Processar cada arquivo XML extraído
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.xml'):
                            xml_path = os.path.join(root, file)
                            try:
                                self._processar_xml(self.empresa, self.nsu, xml_path, resultados)
                            except Exception as e:
                                resultados['erros'].append({
                                    'arquivo': file,
                                    'erro': str(e)
                                })

        return resultados

    def _processar_xml(self, empresa, nsu, xml_path, resultados):
        """Processa um arquivo XML individual e roteia para o endpoint correto"""
        # Ler e analisar o XML para determinar o tipo
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        # Determinar o tipo do XML pela raiz - IGNORAR O NOME DO ARQUIVO
        root_element = self._obter_elemento_raiz(xml_content)

        # Salvar o arquivo na pasta media
        nome_arquivo = os.path.basename(xml_path)
        caminho_relativo = self._salvar_arquivo_media(xml_content, nome_arquivo)

        # Roteamento baseado no CONTEÚDO do XML, não no nome do arquivo
        if root_element == 'nfeProc':
            self._enviar_para_nfe(empresa, nsu, caminho_relativo, resultados)
        elif root_element == 'procEventoNFe':
            self._enviar_para_evento(empresa, nsu, caminho_relativo, resultados)
        elif root_element in ['resNFe', 'resEvento']:  # ACEITA AMBOS
            self._enviar_para_resumo(empresa, nsu, caminho_relativo, resultados)
        else:
            raise ValueError(f'Tipo de XML não suportado: {root_element}')

    def _obter_elemento_raiz(self, xml_content):
        """Obtém o elemento raiz do XML"""
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
            return root.tag.split('}')[-1]  # Remove namespace
        except Exception as e:
            raise ValueError(f'Erro ao analisar XML: {str(e)}')

    def _salvar_arquivo_media(self, xml_content, nome_arquivo):
        """Salva o arquivo XML na pasta media e retorna o caminho relativo"""
        media_dir = os.path.join(settings.MEDIA_ROOT, 'xml')
        os.makedirs(media_dir, exist_ok=True)

        caminho_completo = os.path.join(media_dir, nome_arquivo)

        with open(caminho_completo, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        return f'xml/{nome_arquivo}'

    def _enviar_para_nfe(self, empresa, nsu, caminho_relativo, resultados):
        try:
            # Passa o caminho do arquivo
            processor = NFeProcessor(empresa, nsu, caminho_relativo)
            processor.processar()

            if processor:
                resultados['nfe_processadas'] += 1
            else:
                resultados['erros'].append({
                    'arquivo': caminho_relativo,
                    'erro': f'Erro API NFe: {processor}'
                })

        except Exception as e:
            resultados['erros'].append({
                'arquivo': caminho_relativo,
                'erro': f'Erro ao processar NFe: {str(e)}'
            })

    def _enviar_para_evento(self, empresa, nsu, caminho_relativo, resultados):
        """Envia para o endpoint de eventos"""
        try:
            # Passa o caminho do arquivo
            processor = EventoNFeProcessor(empresa, nsu, caminho_relativo)
            processor.processar()

            if processor:
                resultados['eventos_processados'] += 1
            else:
                resultados['erros'].append({
                    'arquivo': caminho_relativo,
                    'erro': f'Erro API NFe: {processor}'
                })

        except Exception as e:
            resultados['erros'].append({
                'arquivo': caminho_relativo,
                'erro': f'Erro ao processar Evento: {str(e)}'
            })

    def _enviar_para_resumo(self, empresa, nsu, caminho_relativo, resultados):
        """Envia para o endpoint de resumos"""
        try:
            # Passa o caminho do arquivo
            processor = ResumoNFeProcessor(empresa, nsu, caminho_relativo)
            processor.processar()

            if processor:
                resultados['resumos_processados'] += 1
            else:
                resultados['erros'].append({
                    'arquivo': caminho_relativo,
                    'erro': f'Erro API NFe: {processor}'
                })

        except Exception as e:
            resultados['erros'].append({
                'arquivo': caminho_relativo,
                'erro': f'Erro ao processar Resumo: {str(e)}'
            })
