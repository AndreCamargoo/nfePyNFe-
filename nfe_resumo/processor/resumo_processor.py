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
        self.tipo_documento = self._identificar_tipo_documento()

    def _abrir_arquivo(self, caminho_relativo):
        if caminho_relativo.startswith('media/'):
            caminho_relativo = caminho_relativo[6:]

        caminho_completo = os.path.join(settings.MEDIA_ROOT, caminho_relativo)

        if not os.path.exists(caminho_completo):
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_completo}")

        with open(caminho_completo, 'r', encoding='utf-8') as file:
            return file.read()

    def _parse_xml(self):
        try:
            return ET.fromstring(self.xml)
        except ET.ParseError as e:
            raise ValueError(f"Erro ao processar o XML: {str(e)}")

    def _identificar_tipo_documento(self):
        """Identifica se é resNFe ou resEvento"""
        root_tag = self.root.tag.split('}')[-1]
        if root_tag == 'resNFe':
            return 'resNFe'
        elif root_tag == 'resEvento':
            return 'resEvento'
        else:
            raise ValueError(f'Tipo de documento não suportado: {root_tag}')

    def processar(self):
        with transaction.atomic():
            self._criar_historico_nsu()
            if self.tipo_documento == 'resNFe':
                return self._criar_resumo_nfe()
            else:
                return self._criar_resumo_evento()

    def _criar_historico_nsu(self):
        HistoricoNSU.objects.create(empresa=self.empresa, nsu=self.nsu)

    def _criar_resumo_nfe(self):
        """Cria resumo de NFe (resNFe) com tratamento de duplicidade"""
        def safe_findtext(path, default=''):
            found = self.root.find(path, self.ns)
            return found.text if found is not None else default

        chave_nfe = safe_findtext('nfe:chNFe')

        # Verificar se já existe
        if ResumoNFe.objects.filter(chave_nfe=chave_nfe, tipo_documento='resNFe').exists():
            # Atualizar o existente
            resumo = ResumoNFe.objects.get(chave_nfe=chave_nfe, tipo_documento='resNFe')
            resumo.cnpj_emitente = safe_findtext('nfe:CNPJ')
            resumo.nome_emitente = safe_findtext('nfe:xNome')
            resumo.inscricao_estadual = safe_findtext('nfe:IE')
            resumo.data_emissao = safe_findtext('nfe:dhEmi')
            resumo.tipo_nf = int(safe_findtext('nfe:tpNF', '1'))
            resumo.valor_nf = safe_findtext('nfe:vNF', '0')
            resumo.digest_value = safe_findtext('nfe:digVal')
            resumo.data_recebimento = safe_findtext('nfe:dhRecbto')
            resumo.numero_protocolo = safe_findtext('nfe:nProt')
            resumo.situacao_nfe = int(safe_findtext('nfe:cSitNFe', '1'))
            resumo.file_xml = self.file_xml
            resumo.save()
            return resumo

        # Criar novo
        return ResumoNFe.objects.create(
            empresa=self.empresa,
            chave_nfe=chave_nfe,
            tipo_documento='resNFe',
            cnpj_emitente=safe_findtext('nfe:CNPJ'),
            nome_emitente=safe_findtext('nfe:xNome'),
            inscricao_estadual=safe_findtext('nfe:IE'),
            data_emissao=safe_findtext('nfe:dhEmi'),
            tipo_nf=int(safe_findtext('nfe:tpNF', '1')),
            valor_nf=safe_findtext('nfe:vNF', '0'),
            digest_value=safe_findtext('nfe:digVal'),
            data_recebimento=safe_findtext('nfe:dhRecbto'),
            numero_protocolo=safe_findtext('nfe:nProt'),
            situacao_nfe=int(safe_findtext('nfe:cSitNFe', '1')),
            file_xml=self.file_xml
        )

    def _criar_resumo_evento(self):
        """Cria resumo de Evento (resEvento) com tratamento de duplicidade"""
        def safe_findtext(path, default=''):
            found = self.root.find(path, self.ns)
            return found.text if found is not None else default

        chave_nfe = safe_findtext('nfe:chNFe')
        tipo_evento = safe_findtext('nfe:tpEvento')
        sequencia_evento = int(safe_findtext('nfe:nSeqEvento', '0'))

        # Verificar se já existe
        if ResumoNFe.objects.filter(
            chave_nfe=chave_nfe,
            tipo_documento='resEvento',
            tipo_evento=tipo_evento,
            sequencia_evento=sequencia_evento
        ).exists():
            # Atualizar o existente
            resumo = ResumoNFe.objects.get(
                chave_nfe=chave_nfe,
                tipo_documento='resEvento',
                tipo_evento=tipo_evento,
                sequencia_evento=sequencia_evento
            )
            resumo.cnpj_emitente = safe_findtext('nfe:CNPJ')
            resumo.data_recebimento = safe_findtext('nfe:dhRecbto')
            resumo.numero_protocolo = safe_findtext('nfe:nProt')
            resumo.descricao_evento = safe_findtext('nfe:xEvento')
            resumo.orgao = safe_findtext('nfe:cOrgao')
            resumo.file_xml = self.file_xml
            resumo.save()
            return resumo

        # Criar novo
        return ResumoNFe.objects.create(
            empresa=self.empresa,
            chave_nfe=chave_nfe,
            tipo_documento='resEvento',
            cnpj_emitente=safe_findtext('nfe:CNPJ'),
            data_recebimento=safe_findtext('nfe:dhRecbto'),
            numero_protocolo=safe_findtext('nfe:nProt'),
            tipo_evento=tipo_evento,
            sequencia_evento=sequencia_evento,
            descricao_evento=safe_findtext('nfe:xEvento'),
            orgao=safe_findtext('nfe:cOrgao'),
            file_xml=self.file_xml
        )
