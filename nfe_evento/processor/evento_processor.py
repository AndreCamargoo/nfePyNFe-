import os
from django.conf import settings
from django.db import transaction
import xml.etree.ElementTree as ET
from empresa.models import HistoricoNSU
from nfe_evento.models import EventoNFe, SignatureEvento, RetornoEvento


class EventoNFeProcessor:
    def __init__(self, empresa, nsu, file_xml):
        self.empresa = empresa
        self.nsu = nsu
        self.file_xml = file_xml
        self.ns = {
            'nfe': 'http://www.portalfiscal.inf.br/nfe',
            'ds': 'http://www.w3.org/2000/09/xmldsig#'
        }
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
        """Processa o evento NFe"""
        with transaction.atomic():
            self._criar_historico_nsu()
            evento = self._criar_evento()
            self._criar_signature(evento)
            self._criar_retorno(evento)
            return evento

    def _criar_historico_nsu(self):
        """Cria o histórico de NSU"""
        HistoricoNSU.objects.create(empresa=self.empresa, nsu=self.nsu)

    def _criar_evento(self):
        """Cria o evento principal"""
        inf_evento = self.root.find('.//nfe:infEvento', self.ns)
        det_evento = self.root.find('.//nfe:detEvento', self.ns)

        # Função auxiliar para buscar texto seguro
        def safe_findtext(element, path, default=''):
            found = element.find(path, self.ns) if element is not None else None
            return found.text if found is not None else default

        def safe_root_findtext(path, default=''):
            found = self.root.find(path, self.ns)
            return found.text if found is not None else default

        return EventoNFe.objects.create(
            empresa=self.empresa,
            chave_nfe=safe_findtext(inf_evento, 'nfe:chNFe'),
            tipo_evento=safe_findtext(inf_evento, 'nfe:tpEvento'),
            sequencia_evento=int(safe_findtext(inf_evento, 'nfe:nSeqEvento', '0')),
            data_hora_evento=safe_findtext(inf_evento, 'nfe:dhEvento'),
            data_hora_registro=safe_root_findtext('.//nfe:dhRegEvento'),
            descricao_evento=safe_findtext(det_evento, 'nfe:descEvento'),
            numero_protocolo=safe_root_findtext('.//nfe:nProt'),
            status=safe_root_findtext('.//nfe:cStat'),
            motivo=safe_root_findtext('.//nfe:xMotivo'),
            versao_aplicativo=safe_root_findtext('.//nfe:verAplic'),
            orgao=safe_findtext(inf_evento, 'nfe:cOrgao'),
            ambiente=int(safe_findtext(inf_evento, 'nfe:tpAmb', '1')),
            cnpj_destinatario=safe_findtext(inf_evento, 'nfe:CNPJ'),
            file_xml=self.file_xml
        )

    def _criar_signature(self, evento):
        """Cria a assinatura digital"""
        signature = self.root.find('.//ds:Signature', self.ns)
        if signature:
            # Usando find() para elementos e get() para atributos
            signed_info = signature.find('ds:SignedInfo', self.ns)

            canonicalization_el = signed_info.find('ds:CanonicalizationMethod', self.ns) if signed_info else None
            signature_el = signed_info.find('ds:SignatureMethod', self.ns) if signed_info else None

            reference = signed_info.find('ds:Reference', self.ns) if signed_info else None
            digest_method_el = reference.find('ds:DigestMethod', self.ns) if reference else None

            SignatureEvento.objects.create(
                evento=evento,
                signature_value=signature.findtext('ds:SignatureValue', namespaces=self.ns),
                canonicalization_method=canonicalization_el.get('Algorithm') if canonicalization_el else '',
                signature_method=signature_el.get('Algorithm') if signature_el else '',
                digest_method=digest_method_el.get('Algorithm') if digest_method_el else '',
                digest_value=reference.findtext('ds:DigestValue', namespaces=self.ns) if reference else '',
                x509_certificate=signature.findtext('.//ds:X509Certificate', namespaces=self.ns)
            )

    def _criar_retorno(self, evento):
        """Cria o retorno do evento"""
        ret_evento = self.root.find('.//nfe:retEvento/nfe:infEvento', self.ns)

        if ret_evento:
            RetornoEvento.objects.create(
                evento=evento,
                tp_amb=int(ret_evento.findtext('nfe:tpAmb', namespaces=self.ns) or 1),
                ver_aplic=ret_evento.findtext('nfe:verAplic', namespaces=self.ns),
                c_orgao=ret_evento.findtext('nfe:cOrgao', namespaces=self.ns),
                c_stat=ret_evento.findtext('nfe:cStat', namespaces=self.ns),
                x_motivo=ret_evento.findtext('nfe:xMotivo', namespaces=self.ns),
                ch_nfe=ret_evento.findtext('nfe:chNFe', namespaces=self.ns),
                tp_evento=ret_evento.findtext('nfe:tpEvento', namespaces=self.ns),
                x_evento=ret_evento.findtext('nfe:xEvento', namespaces=self.ns),
                n_seq_evento=int(ret_evento.findtext('nfe:nSeqEvento', namespaces=self.ns) or 0),
                cnpj_dest=ret_evento.findtext('nfe:CNPJDest', namespaces=self.ns),
                dh_reg_evento=ret_evento.findtext('nfe:dhRegEvento', namespaces=self.ns),
                n_prot=ret_evento.findtext('nfe:nProt', namespaces=self.ns)
            )
