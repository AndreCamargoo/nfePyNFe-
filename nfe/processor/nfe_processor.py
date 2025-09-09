import os

from django.conf import settings
from django.db import transaction

import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from empresa.models import HistoricoNSU
from nfe.models import (
    NotaFiscal, Ide, Emitente, Destinatario, Produto,
    Imposto, Total, Transporte, Cobranca, Pagamento
)


class NFeProcessor:
    def __init__(self, empresa, nsu, fileXml):
        self.empresa = empresa
        self.nsu = nsu
        self.fileXml = fileXml  # Caminho do arquivo XML
        self.ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        self.xml = self._abrir_arquivo(fileXml)  # Lê o conteúdo do arquivo XML
        self.root = self._parse_xml()
        self.infNFe = None

    def _abrir_arquivo(self, caminho_relativo):
        """Constrói o caminho completo usando MEDIA_ROOT e abre o arquivo XML"""
        # Remove 'media/' se estiver presente no caminho relativo
        if caminho_relativo.startswith('media/'):
            caminho_relativo = caminho_relativo[6:]  # Remove "media/"

        # Constrói o caminho completo
        caminho_completo = os.path.join(settings.MEDIA_ROOT, caminho_relativo)

        if not os.path.exists(caminho_completo):
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_completo}")

        with open(caminho_completo, 'r', encoding='utf-8') as file:
            return file.read()

    def _parse_xml(self):
        """Processa o XML e retorna a raiz do documento"""
        try:
            return ET.fromstring(self.xml)
        except ET.ParseError as e:
            raise ValueError(f"Erro ao processar o XML: {str(e)}")

    def processar(self, debug=False):
        """Processa o XML e realiza os registros no banco"""
        if debug:
            print(self.xml)
            return None

        with transaction.atomic():
            self._criar_historico_nsu()
            nota = self._criar_nota_fiscal()
            self._criar_ide(nota)
            self._criar_emitente(nota)
            self._criar_destinatario(nota)
            self._criar_produto_impostos(nota)
            self._criar_total(nota)
            self._criar_transporte(nota)
            cobranca = self._criar_cobranca(nota)
            self._criar_pagamento(cobranca)
            return nota

    @staticmethod
    def _safe_decimal(text):
        try:
            return Decimal(text)
        except (TypeError, InvalidOperation):
            return Decimal('0')

    @staticmethod
    def _safe_int(text, default=0):
        try:
            return int(text)
        except (TypeError, ValueError):
            return default

    def _criar_historico_nsu(self):
        """Cria o histórico de NSU"""
        HistoricoNSU.objects.create(empresa=self.empresa, nsu=self.nsu)

    def _criar_nota_fiscal(self):
        """Cria a nota fiscal no banco a partir do XML"""
        # Tenta diferentes caminhos para encontrar o infNFe
        inf_nfe_paths = [
            './/nfe:infNFe',  # Para XMLs dentro de nfeProc
            'nfe:infNFe',     # Para XMLs diretos
            './/infNFe',      # Fallback sem namespace
            'infNFe'          # Fallback sem namespace
        ]

        self.infNFe = None
        for path in inf_nfe_paths:
            self.infNFe = self.root.find(path, namespaces=self.ns)
            if self.infNFe is not None:
                break

        if self.infNFe is None:
            raise ValueError("Elemento infNFe não encontrado no XML")

        # Buscar o elemento ide para pegar dhEmi e dhSaiEnt
        ide_el = self.infNFe.find('nfe:ide', namespaces=self.ns)

        # Função auxiliar para buscar texto seguro
        def safe_findtext(element, path, default=None):
            if element is None:
                return default
            found = element.find(path, namespaces=self.ns)
            return found.text if found is not None else default

        # Verifica se já existe uma nota fiscal com a mesma chave (e não deletada)
        chave_nfe = self.infNFe.attrib.get('Id', '').replace('NFe', '')
        nota_existente = NotaFiscal.objects.filter(chave=chave_nfe).first()

        if nota_existente:
            # Se a nota fiscal já existe e está marcada como deletada, reativa a nota
            if nota_existente.deleted_at:
                # Remove a data de deletação para reativar a nota
                nota_existente.deleted_at = None
                nota_existente.save()
                return nota_existente
            else:
                # Caso contrário, cria uma nova nota fiscal (pois a chave é única)
                return NotaFiscal.objects.create(
                    chave=chave_nfe,
                    versao=self.infNFe.attrib.get('versao', ''),
                    dhEmi=safe_findtext(ide_el, 'nfe:dhEmi'),
                    dhSaiEnt=safe_findtext(ide_el, 'nfe:dhSaiEnt'),
                    tpAmb=1,
                    empresa=self.empresa,
                    fileXml=self.fileXml
                )
        else:
            # Se não existir nenhuma nota com essa chave, cria uma nova
            return NotaFiscal.objects.create(
                chave=self.infNFe.attrib.get('Id', '').replace('NFe', ''),
                versao=self.infNFe.attrib.get('versao', ''),
                dhEmi=safe_findtext(ide_el, 'nfe:dhEmi'),
                dhSaiEnt=safe_findtext(ide_el, 'nfe:dhSaiEnt'),
                tpAmb=1,
                empresa=self.empresa,
                fileXml=self.fileXml
            )

    def _criar_ide(self, nota_fiscal):
        ide_el = self.infNFe.find('.//nfe:ide', namespaces=self.ns)
        if ide_el is None:
            raise ValueError("Elemento <ide> não encontrado no XML")

        return Ide.objects.create(
            nota_fiscal=nota_fiscal,
            cUF=ide_el.findtext('nfe:cUF', namespaces=self.ns),
            natOp=ide_el.findtext('nfe:natOp', namespaces=self.ns),
            mod=ide_el.findtext('nfe:mod', namespaces=self.ns),
            serie=ide_el.findtext('nfe:serie', namespaces=self.ns),
            nNF=ide_el.findtext('nfe:nNF', namespaces=self.ns),
            tpNF=self._safe_int(ide_el.findtext('nfe:tpNF', namespaces=self.ns)),
            idDest=self._safe_int(ide_el.findtext('nfe:idDest', namespaces=self.ns)),
            cMunFG=ide_el.findtext('nfe:cMunFG', namespaces=self.ns),
            tpImp=self._safe_int(ide_el.findtext('nfe:tpImp', namespaces=self.ns)),
            tpEmis=self._safe_int(ide_el.findtext('nfe:tpEmis', namespaces=self.ns)),
            cDV=ide_el.findtext('nfe:cDV', namespaces=self.ns),
            finNFe=self._safe_int(ide_el.findtext('nfe:finNFe', namespaces=self.ns)),
            indFinal=self._safe_int(ide_el.findtext('nfe:indFinal', namespaces=self.ns)),
            indPres=self._safe_int(ide_el.findtext('nfe:indPres', namespaces=self.ns)),
            indIntermed=self._safe_int(ide_el.findtext('nfe:indIntermed', namespaces=self.ns)),
            procEmi=self._safe_int(ide_el.findtext('nfe:procEmi', namespaces=self.ns)),
            verProc=ide_el.findtext('nfe:verProc', namespaces=self.ns)
        )

    def _criar_emitente(self, nota_fiscal):
        emit_el = self.infNFe.find('nfe:emit', namespaces=self.ns)
        enderEmit_el = emit_el.find('nfe:enderEmit', namespaces=self.ns)
        crt_el = emit_el.find('nfe:CRT', namespaces=self.ns)
        return Emitente.objects.create(
            nota_fiscal=nota_fiscal,
            CNPJ=emit_el.findtext('nfe:CNPJ', namespaces=self.ns),
            xNome=emit_el.findtext('nfe:xNome', namespaces=self.ns),
            xFant=emit_el.findtext('nfe:xFant', namespaces=self.ns),
            IE=emit_el.findtext('nfe:IE', namespaces=self.ns),
            CRT=self._safe_int(crt_el.text) if crt_el is not None else 0,
            xLgr=enderEmit_el.findtext('nfe:xLgr', namespaces=self.ns),
            nro=enderEmit_el.findtext('nfe:nro', namespaces=self.ns),
            xBairro=enderEmit_el.findtext('nfe:xBairro', namespaces=self.ns),
            cMun=enderEmit_el.findtext('nfe:cMun', namespaces=self.ns),
            xMun=enderEmit_el.findtext('nfe:xMun', namespaces=self.ns),
            UF=enderEmit_el.findtext('nfe:UF', namespaces=self.ns),
            CEP=enderEmit_el.findtext('nfe:CEP', namespaces=self.ns),
            cPais=enderEmit_el.findtext('nfe:cPais', namespaces=self.ns),
            xPais=enderEmit_el.findtext('nfe:xPais', namespaces=self.ns),
            fone=enderEmit_el.findtext('nfe:fone', namespaces=self.ns),
        )

    def _criar_destinatario(self, nota_fiscal):
        dest_el = self.infNFe.find('nfe:dest', namespaces=self.ns)
        enderDest_el = dest_el.find('nfe:enderDest', namespaces=self.ns)

        return Destinatario.objects.create(
            nota_fiscal=nota_fiscal,
            CNPJ=dest_el.findtext('nfe:CNPJ', namespaces=self.ns),
            xNome=dest_el.findtext('nfe:xNome', namespaces=self.ns),
            IE=dest_el.findtext('nfe:IE', namespaces=self.ns),
            indIEDest=self._safe_int(dest_el.findtext('nfe:indIEDest', namespaces=self.ns)),
            xLgr=enderDest_el.findtext('nfe:xLgr', namespaces=self.ns),
            nro=enderDest_el.findtext('nfe:nro', namespaces=self.ns),
            xCpl=enderDest_el.findtext('nfe:xCpl', namespaces=self.ns),
            xBairro=enderDest_el.findtext('nfe:xBairro', namespaces=self.ns),
            cMun=enderDest_el.findtext('nfe:cMun', namespaces=self.ns),
            xMun=enderDest_el.findtext('nfe:xMun', namespaces=self.ns),
            UF=enderDest_el.findtext('nfe:UF', namespaces=self.ns),
            CEP=enderDest_el.findtext('nfe:CEP', namespaces=self.ns),
            cPais=enderDest_el.findtext('nfe:cPais', namespaces=self.ns),
            xPais=enderDest_el.findtext('nfe:xPais', namespaces=self.ns),
        )

    def _criar_produto_impostos(self, nota_fiscal):
        for det in self.infNFe.findall('nfe:det', namespaces=self.ns):
            prod_el = det.find('nfe:prod', namespaces=self.ns)

            produto = Produto.objects.create(
                nota_fiscal=nota_fiscal,
                nItem=self._safe_int(det.attrib.get('nItem')),
                cProd=prod_el.findtext('nfe:cProd', namespaces=self.ns),
                cEAN=prod_el.findtext('nfe:cEAN', namespaces=self.ns),
                xProd=prod_el.findtext('nfe:xProd', namespaces=self.ns),
                NCM=prod_el.findtext('nfe:NCM', namespaces=self.ns),
                CFOP=prod_el.findtext('nfe:CFOP', namespaces=self.ns),
                uCom=prod_el.findtext('nfe:uCom', namespaces=self.ns),
                qCom=self._safe_decimal(prod_el.findtext('nfe:qCom', namespaces=self.ns)),
                vUnCom=self._safe_decimal(prod_el.findtext('nfe:vUnCom', namespaces=self.ns)),
                vProd=self._safe_decimal(prod_el.findtext('nfe:vProd', namespaces=self.ns)),
                uTrib=prod_el.findtext('nfe:uTrib', namespaces=self.ns),
                qTrib=self._safe_decimal(prod_el.findtext('nfe:qTrib', namespaces=self.ns)),
                vUnTrib=self._safe_decimal(prod_el.findtext('nfe:vUnTrib', namespaces=self.ns)),
                indTot=self._safe_int(prod_el.findtext('nfe:indTot', namespaces=self.ns)),
            )

            imposto_el = det.find('nfe:imposto', namespaces=self.ns)

            if imposto_el is not None:
                icms_el = imposto_el.find('nfe:ICMS', namespaces=self.ns)

                if icms_el is not None:
                    icms_key = list(icms_el)[0].tag  # ex: ICMS00, ICMS40
                    icms = icms_el.find(icms_key)

                    if icms is not None:
                        Imposto.objects.create(
                            produto=produto,
                            vTotTrib=self._safe_decimal(imposto_el.findtext('nfe:vTotTrib', '0', namespaces=self.ns)),
                            orig=icms.findtext('nfe:orig', namespaces=self.ns),
                            CST=icms.findtext('nfe:CST', namespaces=self.ns),
                        )

    def _criar_total(self, nota_fiscal):
        total_el = self.infNFe.find('nfe:total', namespaces=self.ns)
        icms_tot_el = total_el.find('nfe:ICMSTot', namespaces=self.ns)

        return Total.objects.create(
            nota_fiscal=nota_fiscal,
            vBC=self._safe_decimal(icms_tot_el.findtext('nfe:vBC', '0', namespaces=self.ns)),
            vICMS=self._safe_decimal(icms_tot_el.findtext('nfe:vICMS', '0', namespaces=self.ns)),
            vICMSDeson=self._safe_decimal(icms_tot_el.findtext('nfe:vICMSDeson', '0', namespaces=self.ns)),
            vFCP=self._safe_decimal(icms_tot_el.findtext('nfe:vFCP', '0', namespaces=self.ns)),
            vBCST=self._safe_decimal(icms_tot_el.findtext('nfe:vBCST', '0', namespaces=self.ns)),
            vST=self._safe_decimal(icms_tot_el.findtext('nfe:vST', '0', namespaces=self.ns)),
            vFCPST=self._safe_decimal(icms_tot_el.findtext('nfe:vFCPST', '0', namespaces=self.ns)),
            vFCPSTRet=self._safe_decimal(icms_tot_el.findtext('nfe:vFCPSTRet', '0', namespaces=self.ns)),
            vProd=self._safe_decimal(icms_tot_el.findtext('nfe:vProd', '0', namespaces=self.ns)),
            vFrete=self._safe_decimal(icms_tot_el.findtext('nfe:vFrete', '0', namespaces=self.ns)),
            vSeg=self._safe_decimal(icms_tot_el.findtext('nfe:vSeg', '0', namespaces=self.ns)),
            vDesc=self._safe_decimal(icms_tot_el.findtext('nfe:vDesc', '0', namespaces=self.ns)),
            vII=self._safe_decimal(icms_tot_el.findtext('nfe:vII', '0', namespaces=self.ns)),
            vIPI=self._safe_decimal(icms_tot_el.findtext('nfe:vIPI', '0', namespaces=self.ns)),
            vIPIDevol=self._safe_decimal(icms_tot_el.findtext('nfe:vIPIDevol', '0', namespaces=self.ns)),
            vPIS=self._safe_decimal(icms_tot_el.findtext('nfe:vPIS', '0', namespaces=self.ns)),
            vCOFINS=self._safe_decimal(icms_tot_el.findtext('nfe:vCOFINS', '0', namespaces=self.ns)),
            vOutro=self._safe_decimal(icms_tot_el.findtext('nfe:vOutro', '0', namespaces=self.ns)),
            vNF=self._safe_decimal(icms_tot_el.findtext('nfe:vNF', '0', namespaces=self.ns)),
            vTotTrib=self._safe_decimal(icms_tot_el.findtext('nfe:vTotTrib', '0', namespaces=self.ns)),
        )

    def _criar_transporte(self, nota_fiscal):
        transp_el = self.infNFe.find('nfe:transp', namespaces=self.ns)
        vol_el = transp_el.find('nfe:vol', namespaces=self.ns) if transp_el is not None else None

        return Transporte.objects.create(
            nota_fiscal=nota_fiscal,
            modFrete=self._safe_int(transp_el.findtext('nfe:modFrete', '0', namespaces=self.ns)) if transp_el is not None else 0,
            qVol=self._safe_int(vol_el.findtext('nfe:qVol', '0', namespaces=self.ns)) if vol_el is not None else None,
        )

    def _criar_cobranca(self, nota_fiscal):
        cobr_el = self.infNFe.find('nfe:cobr', namespaces=self.ns)
        fat_el = cobr_el.find('nfe:fat', namespaces=self.ns) if cobr_el is not None else None

        return Cobranca.objects.create(
            nota_fiscal=nota_fiscal,
            nFat=fat_el.findtext('nFat', namespaces=self.ns) if fat_el is not None else None,
            vOrig=self._safe_decimal(fat_el.findtext('vOrig', '0', namespaces=self.ns)) if fat_el is not None else None,
            vDesc=self._safe_decimal(fat_el.findtext('vDesc', '0', namespaces=self.ns)) if fat_el is not None else None,
            vLiq=self._safe_decimal(fat_el.findtext('vLiq', '0', namespaces=self.ns)) if fat_el is not None else None,
        )

    def _criar_pagamento(self, cobranca):
        pagto_list = []
        cobr_el = self.infNFe.find('nfe:cobr', namespaces=self.ns)

        if cobr_el is not None:
            for pag_el in cobr_el.findall('nfe:pag', namespaces=self.ns):
                tPag = pag_el.findtext('nfe:tPag', namespaces=self.ns)
                vPag = self._safe_decimal(pag_el.findtext('nfe:vPag', '0', namespaces=self.ns))

                pag = Pagamento.objects.create(
                    cobranca=cobranca,
                    tPag=tPag,
                    vPag=vPag
                )

                pagto_list.append(pag)
