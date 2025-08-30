import os
from django.conf import settings
from django.db import transaction
import xml.etree.ElementTree as ET
from empresa.models import HistoricoNSU
from nfe_resumo.models import ResumoNFe


class ResumoNFeProcessor:
    def __init__(self, empresa, nsu, file_xml):
        self.empresa = empresa
        self.nsu = nsu
        self.file_xml = file_xml
        self.ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        self.xml = self._abrir_arquivo(file_xml)
        self.root = self._parse_xml()

    def _abrir_arquivo(self, caminho_relativo):
        """Abre o arquivo XML"""
        if caminho_relativo.startswith('media/'):
            caminho_relativo = caminho_relativo[6:]

        caminho_completo = os.path.join(settings.MEDIA_ROOT, caminho_relativo)

        if not os.path.exists(caminho_completo):
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_completo}")

        with open(caminho_completo, 'r', encoding='utf-8') as file:
            return file.read()

    def _parse_xml(self):
        """Processa o XML"""
        try:
            return ET.fromstring(self.xml)
        except ET.ParseError as e:
            raise ValueError(f"Erro ao processar o XML: {str(e)}")

    def processar(self):
        """Processa o resumo NFe"""
        with transaction.atomic():
            self._criar_historico_nsu()
            resumo = self._criar_resumo()
            return resumo

    def _criar_historico_nsu(self):
        """Cria o histórico de NSU"""
        HistoricoNSU.objects.create(empresa=self.empresa, nsu=self.nsu)

    def _criar_resumo(self):
        """Cria o resumo NFe no banco"""
        # Função auxiliar para buscar texto seguro
        def safe_findtext(element, path, default=''):
            found = element.find(path, self.ns) if element is not None else None
            return found.text if found is not None else default

        return ResumoNFe.objects.create(
            empresa=self.empresa,
            chave_nfe=safe_findtext(self.root, 'nfe:chNFe'),
            cnpj_emitente=safe_findtext(self.root, 'nfe:CNPJ'),
            nome_emitente=safe_findtext(self.root, 'nfe:xNome'),
            inscricao_estadual=safe_findtext(self.root, 'nfe:IE'),
            data_emissao=safe_findtext(self.root, 'nfe:dhEmi'),
            tipo_nf=int(safe_findtext(self.root, 'nfe:tpNF', '1')),
            valor_nf=safe_findtext(self.root, 'nfe:vNF', '0'),
            digest_value=safe_findtext(self.root, 'nfe:digVal'),
            data_recebimento=safe_findtext(self.root, 'nfe:dhRecbto'),
            numero_protocolo=safe_findtext(self.root, 'nfe:nProt'),
            situacao_nfe=int(safe_findtext(self.root, 'nfe:cSitNFe', '1')),
            file_xml=self.file_xml
        )
