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

from db_allnube_empresa.utils.database_utils import DatabaseManager
from db_allnube_empresa.models import (
    NotaFiscalFlat, IdeFlat, EmitenteFlat, DestinatarioFlat, ProdutoFlat,
    ImpostoFlat, TotalFlat, TransporteFlat, CobrancaFlat, PagamentoFlat
)


class NFeProcessor:
    def __init__(self, empresa, nsu, fileXml):
        self.empresa = empresa
        self.nsu = nsu
        self.fileXml = fileXml
        self.ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        self.xml = self._abrir_arquivo(fileXml)
        self.root = self._parse_xml()
        self.infNFe = None
        # self.bancoProprio = DatabaseManager.empresa_tem_banco_proprio(self.empresa.id)
        self.nota_existia_default = False
        self.nota_existia_empresa = False

    def _abrir_arquivo(self, caminho_relativo):
        """Constrói o caminho completo usando MEDIA_ROOT e abre o arquivo XML"""
        if caminho_relativo.startswith('media/'):
            caminho_relativo = caminho_relativo[6:]

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
        """Processa o XML e realiza os registros nos bancos"""
        if debug:
            print(self.xml)
            return None

        with transaction.atomic():
            self._criar_historico_nsu()

            # Processa no banco DEFAULT (SEMPRE)
            nota_default = self._criar_nota_fiscal_default()

            # Só cria os relacionados se a nota NÃO existia anteriormente
            if nota_default and not self.nota_existia_default:
                self._criar_ide_default(nota_default)
                self._criar_emitente_default(nota_default)
                self._criar_destinatario_default(nota_default)
                self._criar_produto_impostos_default(nota_default)
                self._criar_total_default(nota_default)
                self._criar_transporte_default(nota_default)
                cobranca_default = self._criar_cobranca_default(nota_default)
                self._criar_pagamento_default(cobranca_default)

            # Processa no banco da EMPRESA APENAS SE tiver banco próprio
            nota_empresa = None
            try:
                # Configura banco da empresa se necessário
                success = DatabaseManager.usar_banco_empresa(self.empresa.id)
                if success:
                    nota_empresa = self._criar_nota_fiscal_empresa()

                    # Só cria os relacionados se a nota NÃO existia anteriormente
                    if nota_empresa and not self.nota_existia_empresa:
                        self._criar_ide_empresa(nota_empresa)
                        self._criar_emitente_empresa(nota_empresa)
                        self._criar_destinatario_empresa(nota_empresa)
                        self._criar_produto_impostos_empresa(nota_empresa)
                        self._criar_total_empresa(nota_empresa)
                        self._criar_transporte_empresa(nota_empresa)
                        cobranca_empresa = self._criar_cobranca_empresa(nota_empresa)
                        self._criar_pagamento_empresa(cobranca_empresa)
                else:
                    print(f"AVISO: Não foi possível configurar banco para empresa {self.empresa.id}")
            except Exception as e:
                print(f"ERRO ao processar no banco da empresa {self.empresa.id}: {e}")
                # Continua o processamento mesmo com erro no banco da empresa

            return nota_default if nota_default else nota_empresa

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
        """Cria o histórico de NSU no banco default"""
        HistoricoNSU.objects.create(empresa=self.empresa, nsu=self.nsu)

    def _encontrar_infNFe(self):
        """Encontra o elemento infNFe no XML"""
        inf_nfe_paths = [
            './/nfe:infNFe',
            'nfe:infNFe',
            './/infNFe',
            'infNFe'
        ]

        for path in inf_nfe_paths:
            self.infNFe = self.root.find(path, namespaces=self.ns)
            if self.infNFe is not None:
                break

        if self.infNFe is None:
            raise ValueError("Elemento infNFe não encontrado no XML")
        return self.infNFe

    def _safe_findtext(self, element, path, default=None):
        """Busca texto seguro em elemento XML"""
        if element is None:
            return default
        found = element.find(path, namespaces=self.ns)
        return found.text if found is not None else default

    # ========== MÉTODOS PARA BANCO DEFAULT ==========

    def _criar_nota_fiscal_default(self):
        """Cria nota fiscal no banco DEFAULT"""
        self._encontrar_infNFe()
        ide_el = self.infNFe.find('nfe:ide', namespaces=self.ns)
        chave_nfe = self.infNFe.attrib.get('Id', '').replace('NFe', '')

        # Verifica se já existe
        nota_existente = NotaFiscal.objects.filter(chave=chave_nfe).first()
        if nota_existente:
            # MARCA QUE A NOTA JÁ EXISTIA (independente de estar deletada ou não)
            self.nota_existia_default = True

            if nota_existente.deleted_at:
                # Remove a data de deletação para reativar a nota
                nota_existente.deleted_at = None
                nota_existente.save()
            return nota_existente

        # Cria nova nota
        self.nota_existia_default = False
        return NotaFiscal.objects.create(
            chave=chave_nfe,
            versao=self.infNFe.attrib.get('versao', ''),
            dhEmi=self._safe_findtext(ide_el, 'nfe:dhEmi'),
            dhSaiEnt=self._safe_findtext(ide_el, 'nfe:dhSaiEnt'),
            tpAmb=1,
            empresa=self.empresa,
            fileXml=self.fileXml
        )

    def _criar_ide_default(self, nota):
        """Cria IDE no banco DEFAULT"""
        ide_el = self.infNFe.find('nfe:ide', namespaces=self.ns)
        if ide_el is None:
            return

        Ide.objects.create(
            nota_fiscal=nota,
            cUF=self._safe_findtext(ide_el, 'nfe:cUF'),
            natOp=self._safe_findtext(ide_el, 'nfe:natOp'),
            mod=self._safe_findtext(ide_el, 'nfe:mod'),
            serie=self._safe_findtext(ide_el, 'nfe:serie'),
            nNF=self._safe_findtext(ide_el, 'nfe:nNF'),
            tpNF=self._safe_int(self._safe_findtext(ide_el, 'nfe:tpNF')),
            idDest=self._safe_int(self._safe_findtext(ide_el, 'nfe:idDest')),
            cMunFG=self._safe_findtext(ide_el, 'nfe:cMunFG'),
            tpImp=self._safe_int(self._safe_findtext(ide_el, 'nfe:tpImp')),
            tpEmis=self._safe_int(self._safe_findtext(ide_el, 'nfe:tpEmis')),
            cDV=self._safe_findtext(ide_el, 'nfe:cDV'),
            finNFe=self._safe_int(self._safe_findtext(ide_el, 'nfe:finNFe')),
            indFinal=self._safe_int(self._safe_findtext(ide_el, 'nfe:indFinal')),
            indPres=self._safe_int(self._safe_findtext(ide_el, 'nfe:indPres')),
            indIntermed=self._safe_int(self._safe_findtext(ide_el, 'nfe:indIntermed')),
            procEmi=self._safe_int(self._safe_findtext(ide_el, 'nfe:procEmi')),
            verProc=self._safe_findtext(ide_el, 'nfe:verProc')
        )

    def _criar_emitente_default(self, nota):
        """Cria emitente no banco DEFAULT"""
        emitente_el = self.infNFe.find('nfe:emit', namespaces=self.ns)
        if emitente_el is None:
            return

        ender_el = emitente_el.find('nfe:enderEmit', namespaces=self.ns)

        Emitente.objects.create(
            nota_fiscal=nota,
            CNPJ=self._safe_findtext(emitente_el, 'nfe:CNPJ'),
            xNome=self._safe_findtext(emitente_el, 'nfe:xNome'),
            xFant=self._safe_findtext(emitente_el, 'nfe:xFant'),
            IE=self._safe_findtext(emitente_el, 'nfe:IE'),
            CRT=self._safe_int(self._safe_findtext(emitente_el, 'nfe:CRT')),
            xLgr=self._safe_findtext(ender_el, 'nfe:xLgr'),
            nro=self._safe_findtext(ender_el, 'nfe:nro'),
            xBairro=self._safe_findtext(ender_el, 'nfe:xBairro'),
            cMun=self._safe_findtext(ender_el, 'nfe:cMun'),
            xMun=self._safe_findtext(ender_el, 'nfe:xMun'),
            UF=self._safe_findtext(ender_el, 'nfe:UF'),
            CEP=self._safe_findtext(ender_el, 'nfe:CEP'),
            cPais=self._safe_findtext(ender_el, 'nfe:cPais'),
            xPais=self._safe_findtext(ender_el, 'nfe:xPais'),
            fone=self._safe_findtext(ender_el, 'nfe:fone')
        )

    def _criar_destinatario_default(self, nota):
        """Cria destinatário no banco DEFAULT"""
        destinatario_el = self.infNFe.find('nfe:dest', namespaces=self.ns)
        if destinatario_el is None:
            return

        ender_el = destinatario_el.find('nfe:enderDest', namespaces=self.ns)

        Destinatario.objects.create(
            nota_fiscal=nota,
            CNPJ=self._safe_findtext(destinatario_el, 'nfe:CNPJ'),
            xNome=self._safe_findtext(destinatario_el, 'nfe:xNome'),
            IE=self._safe_findtext(destinatario_el, 'nfe:IE'),
            indIEDest=self._safe_int(self._safe_findtext(destinatario_el, 'nfe:indIEDest')),
            xLgr=self._safe_findtext(ender_el, 'nfe:xLgr'),
            nro=self._safe_findtext(ender_el, 'nfe:nro'),
            xCpl=self._safe_findtext(ender_el, 'nfe:xCpl'),
            xBairro=self._safe_findtext(ender_el, 'nfe:xBairro'),
            cMun=self._safe_findtext(ender_el, 'nfe:cMun'),
            xMun=self._safe_findtext(ender_el, 'nfe:xMun'),
            UF=self._safe_findtext(ender_el, 'nfe:UF'),
            CEP=self._safe_findtext(ender_el, 'nfe:CEP'),
            cPais=self._safe_findtext(ender_el, 'nfe:cPais'),
            xPais=self._safe_findtext(ender_el, 'nfe:xPais')
        )

    def _criar_produto_impostos_default(self, nota):
        """Cria produtos e impostos no banco DEFAULT"""
        for det in self.infNFe.findall('nfe:det', namespaces=self.ns):
            prod_el = det.find('nfe:prod', namespaces=self.ns)
            if prod_el is None:
                continue

            produto = Produto.objects.create(
                nota_fiscal=nota,
                nItem=self._safe_int(det.attrib.get('nItem')),
                cProd=self._safe_findtext(prod_el, 'nfe:cProd'),
                cEAN=self._safe_findtext(prod_el, 'nfe:cEAN'),
                xProd=self._safe_findtext(prod_el, 'nfe:xProd'),
                NCM=self._safe_findtext(prod_el, 'nfe:NCM'),
                CFOP=self._safe_findtext(prod_el, 'nfe:CFOP'),
                uCom=self._safe_findtext(prod_el, 'nfe:uCom'),
                qCom=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:qCom')),
                vUnCom=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:vUnCom')),
                vProd=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:vProd')),
                uTrib=self._safe_findtext(prod_el, 'nfe:uTrib'),
                qTrib=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:qTrib')),
                vUnTrib=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:vUnTrib')),
                indTot=self._safe_int(self._safe_findtext(prod_el, 'nfe:indTot'))
            )

            # Processa impostos
            self._criar_imposto_default(produto, det)

    def _criar_imposto_default(self, produto, det_el):
        """Cria imposto no banco DEFAULT"""
        imposto_el = det_el.find('nfe:imposto', namespaces=self.ns)
        if imposto_el is None:
            return

        icms_el = imposto_el.find('nfe:ICMS', namespaces=self.ns)
        if icms_el is not None:
            # Pega o primeiro elemento filho (ICMS00, ICMS40, etc.)
            icms_key = next((child for child in icms_el), None)
            if icms_key is not None:
                Imposto.objects.create(
                    produto=produto,
                    vTotTrib=self._safe_decimal(self._safe_findtext(imposto_el, 'nfe:vTotTrib', '0')),
                    orig=self._safe_findtext(icms_key, 'nfe:orig'),
                    CST=self._safe_findtext(icms_key, 'nfe:CST')
                )

    def _criar_total_default(self, nota):
        """Cria totais no banco DEFAULT"""
        total_el = self.infNFe.find('nfe:total', namespaces=self.ns)
        icms_tot_el = total_el.find('nfe:ICMSTot', namespaces=self.ns) if total_el else None

        if icms_tot_el is None:
            return

        Total.objects.create(
            nota_fiscal=nota,
            vBC=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vBC', '0')),
            vICMS=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vICMS', '0')),
            vICMSDeson=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vICMSDeson', '0')),
            vFCP=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vFCP', '0')),
            vBCST=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vBCST', '0')),
            vST=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vST', '0')),
            vFCPST=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vFCPST', '0')),
            vFCPSTRet=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vFCPSTRet', '0')),
            vProd=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vProd', '0')),
            vFrete=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vFrete', '0')),
            vSeg=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vSeg', '0')),
            vDesc=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vDesc', '0')),
            vII=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vII', '0')),
            vIPI=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vIPI', '0')),
            vIPIDevol=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vIPIDevol', '0')),
            vPIS=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vPIS', '0')),
            vCOFINS=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vCOFINS', '0')),
            vOutro=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vOutro', '0')),
            vNF=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vNF', '0')),
            vTotTrib=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vTotTrib', '0'))
        )

    def _criar_transporte_default(self, nota):
        """Cria transporte no banco DEFAULT"""
        transp_el = self.infNFe.find('nfe:transp', namespaces=self.ns)
        if transp_el is None:
            return

        vol_el = transp_el.find('nfe:vol', namespaces=self.ns)

        Transporte.objects.create(
            nota_fiscal=nota,
            modFrete=self._safe_int(self._safe_findtext(transp_el, 'nfe:modFrete', '0')),
            qVol=self._safe_int(self._safe_findtext(vol_el, 'nfe:qVol', '0')) if vol_el else None
        )

    def _criar_cobranca_default(self, nota):
        """Cria cobrança no banco DEFAULT"""
        cobr_el = self.infNFe.find('nfe:cobr', namespaces=self.ns)
        if cobr_el is None:
            return Cobranca.objects.create(nota_fiscal=nota)

        fat_el = cobr_el.find('nfe:fat', namespaces=self.ns)

        return Cobranca.objects.create(
            nota_fiscal=nota,
            nFat=self._safe_findtext(fat_el, 'nfe:nFat') if fat_el else None,
            vOrig=self._safe_decimal(self._safe_findtext(fat_el, 'nfe:vOrig', '0')) if fat_el else None,
            vDesc=self._safe_decimal(self._safe_findtext(fat_el, 'nfe:vDesc', '0')) if fat_el else None,
            vLiq=self._safe_decimal(self._safe_findtext(fat_el, 'nfe:vLiq', '0')) if fat_el else None
        )

    def _criar_pagamento_default(self, cobranca):
        """Cria pagamentos no banco DEFAULT"""
        if cobranca is None:
            return

        cobr_el = self.infNFe.find('nfe:cobr', namespaces=self.ns)
        if cobr_el is None:
            return

        for pag_el in cobr_el.findall('nfe:pag', namespaces=self.ns):
            Pagamento.objects.create(
                cobranca=cobranca,
                tPag=self._safe_findtext(pag_el, 'nfe:tPag'),
                vPag=self._safe_decimal(self._safe_findtext(pag_el, 'nfe:vPag', '0'))
            )

    # ========== MÉTODOS PARA BANCO EMPRESA ==========

    def _criar_nota_fiscal_empresa(self):
        """Cria nota fiscal no banco da EMPRESA"""
        chave_nfe = self.infNFe.attrib.get('Id', '').replace('NFe', '')
        ide_el = self.infNFe.find('nfe:ide', namespaces=self.ns)

        # Verifica se já existe no banco da empresa
        nota_existente = NotaFiscalFlat.objects.filter(chave=chave_nfe).first()
        if nota_existente:
            # MARCA QUE A NOTA JÁ EXISTIA (independente de estar deletada ou não)
            self.nota_existia_empresa = True

            if nota_existente.deleted_at:
                # Remove a data de deletação para reativar a nota
                nota_existente.deleted_at = None
                nota_existente.save()
            return nota_existente

        # Cria nova nota
        self.nota_existia_empresa = False
        return NotaFiscalFlat.objects.create(
            empresa_id=self.empresa.id,
            chave=chave_nfe,
            versao=self.infNFe.attrib.get('versao', ''),
            dhEmi=self._safe_findtext(ide_el, 'nfe:dhEmi'),
            dhSaiEnt=self._safe_findtext(ide_el, 'nfe:dhSaiEnt'),
            tpAmb=1,
            fileXml=self.fileXml
        )

    def _criar_ide_empresa(self, nota):
        """Cria IDE no banco da EMPRESA"""
        ide_el = self.infNFe.find('nfe:ide', namespaces=self.ns)
        if ide_el is None:
            return

        IdeFlat.objects.create(
            nota_fiscal_id=nota.id,
            cUF=self._safe_findtext(ide_el, 'nfe:cUF'),
            natOp=self._safe_findtext(ide_el, 'nfe:natOp'),
            mod=self._safe_findtext(ide_el, 'nfe:mod'),
            serie=self._safe_findtext(ide_el, 'nfe:serie'),
            nNF=self._safe_findtext(ide_el, 'nfe:nNF'),
            tpNF=self._safe_int(self._safe_findtext(ide_el, 'nfe:tpNF')),
            idDest=self._safe_int(self._safe_findtext(ide_el, 'nfe:idDest')),
            cMunFG=self._safe_findtext(ide_el, 'nfe:cMunFG'),
            tpImp=self._safe_int(self._safe_findtext(ide_el, 'nfe:tpImp')),
            tpEmis=self._safe_int(self._safe_findtext(ide_el, 'nfe:tpEmis')),
            cDV=self._safe_findtext(ide_el, 'nfe:cDV'),
            finNFe=self._safe_int(self._safe_findtext(ide_el, 'nfe:finNFe')),
            indFinal=self._safe_int(self._safe_findtext(ide_el, 'nfe:indFinal')),
            indPres=self._safe_int(self._safe_findtext(ide_el, 'nfe:indPres')),
            indIntermed=self._safe_int(self._safe_findtext(ide_el, 'nfe:indIntermed')),
            procEmi=self._safe_int(self._safe_findtext(ide_el, 'nfe:procEmi')),
            verProc=self._safe_findtext(ide_el, 'nfe:verProc')
        )

    def _criar_emitente_empresa(self, nota):
        """Cria emitente no banco da EMPRESA"""
        emitente_el = self.infNFe.find('nfe:emit', namespaces=self.ns)
        if emitente_el is None:
            return

        ender_el = emitente_el.find('nfe:enderEmit', namespaces=self.ns)

        EmitenteFlat.objects.create(
            nota_fiscal_id=nota.id,
            CNPJ=self._safe_findtext(emitente_el, 'nfe:CNPJ'),
            xNome=self._safe_findtext(emitente_el, 'nfe:xNome'),
            xFant=self._safe_findtext(emitente_el, 'nfe:xFant'),
            IE=self._safe_findtext(emitente_el, 'nfe:IE'),
            CRT=self._safe_int(self._safe_findtext(emitente_el, 'nfe:CRT')),
            xLgr=self._safe_findtext(ender_el, 'nfe:xLgr'),
            nro=self._safe_findtext(ender_el, 'nfe:nro'),
            xBairro=self._safe_findtext(ender_el, 'nfe:xBairro'),
            cMun=self._safe_findtext(ender_el, 'nfe:cMun'),
            xMun=self._safe_findtext(ender_el, 'nfe:xMun'),
            UF=self._safe_findtext(ender_el, 'nfe:UF'),
            CEP=self._safe_findtext(ender_el, 'nfe:CEP'),
            cPais=self._safe_findtext(ender_el, 'nfe:cPais'),
            xPais=self._safe_findtext(ender_el, 'nfe:xPais'),
            fone=self._safe_findtext(ender_el, 'nfe:fone')
        )

    def _criar_destinatario_empresa(self, nota):
        """Cria destinatário no banco da EMPRESA"""
        destinatario_el = self.infNFe.find('nfe:dest', namespaces=self.ns)
        if destinatario_el is None:
            return

        ender_el = destinatario_el.find('nfe:enderDest', namespaces=self.ns)

        DestinatarioFlat.objects.create(
            nota_fiscal_id=nota.id,
            CNPJ=self._safe_findtext(destinatario_el, 'nfe:CNPJ'),
            xNome=self._safe_findtext(destinatario_el, 'nfe:xNome'),
            IE=self._safe_findtext(destinatario_el, 'nfe:IE'),
            indIEDest=self._safe_int(self._safe_findtext(destinatario_el, 'nfe:indIEDest')),
            xLgr=self._safe_findtext(ender_el, 'nfe:xLgr'),
            nro=self._safe_findtext(ender_el, 'nfe:nro'),
            xCpl=self._safe_findtext(ender_el, 'nfe:xCpl'),
            xBairro=self._safe_findtext(ender_el, 'nfe:xBairro'),
            cMun=self._safe_findtext(ender_el, 'nfe:cMun'),
            xMun=self._safe_findtext(ender_el, 'nfe:xMun'),
            UF=self._safe_findtext(ender_el, 'nfe:UF'),
            CEP=self._safe_findtext(ender_el, 'nfe:CEP'),
            cPais=self._safe_findtext(ender_el, 'nfe:cPais'),
            xPais=self._safe_findtext(ender_el, 'nfe:xPais')
        )

    def _criar_produto_impostos_empresa(self, nota):
        """Cria produtos e impostos no banco da EMPRESA"""
        for det in self.infNFe.findall('nfe:det', namespaces=self.ns):
            prod_el = det.find('nfe:prod', namespaces=self.ns)
            if prod_el is None:
                continue

            produto = ProdutoFlat.objects.create(
                nota_fiscal_id=nota.id,
                nItem=self._safe_int(det.attrib.get('nItem')),
                cProd=self._safe_findtext(prod_el, 'nfe:cProd'),
                cEAN=self._safe_findtext(prod_el, 'nfe:cEAN'),
                xProd=self._safe_findtext(prod_el, 'nfe:xProd'),
                NCM=self._safe_findtext(prod_el, 'nfe:NCM'),
                CFOP=self._safe_findtext(prod_el, 'nfe:CFOP'),
                uCom=self._safe_findtext(prod_el, 'nfe:uCom'),
                qCom=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:qCom')),
                vUnCom=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:vUnCom')),
                vProd=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:vProd')),
                uTrib=self._safe_findtext(prod_el, 'nfe:uTrib'),
                qTrib=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:qTrib')),
                vUnTrib=self._safe_decimal(self._safe_findtext(prod_el, 'nfe:vUnTrib')),
                indTot=self._safe_int(self._safe_findtext(prod_el, 'nfe:indTot'))
            )

            # Processa impostos
            self._criar_imposto_empresa(produto, det)

    def _criar_imposto_empresa(self, produto, det_el):
        """Cria imposto no banco da EMPRESA"""
        imposto_el = det_el.find('nfe:imposto', namespaces=self.ns)
        if imposto_el is None:
            return

        icms_el = imposto_el.find('nfe:ICMS', namespaces=self.ns)
        if icms_el is not None:
            icms_key = next((child for child in icms_el), None)
            if icms_key is not None:
                ImpostoFlat.objects.create(
                    produto_id=produto.id,
                    vTotTrib=self._safe_decimal(self._safe_findtext(imposto_el, 'nfe:vTotTrib', '0')),
                    orig=self._safe_findtext(icms_key, 'nfe:orig'),
                    CST=self._safe_findtext(icms_key, 'nfe:CST')
                )

    def _criar_total_empresa(self, nota):
        """Cria totais no banco da EMPRESA"""
        total_el = self.infNFe.find('nfe:total', namespaces=self.ns)
        icms_tot_el = total_el.find('nfe:ICMSTot', namespaces=self.ns) if total_el else None

        if icms_tot_el is None:
            return

        TotalFlat.objects.create(
            nota_fiscal_id=nota.id,
            vBC=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vBC', '0')),
            vICMS=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vICMS', '0')),
            vICMSDeson=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vICMSDeson', '0')),
            vFCP=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vFCP', '0')),
            vBCST=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vBCST', '0')),
            vST=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vST', '0')),
            vFCPST=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vFCPST', '0')),
            vFCPSTRet=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vFCPSTRet', '0')),
            vProd=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vProd', '0')),
            vFrete=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vFrete', '0')),
            vSeg=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vSeg', '0')),
            vDesc=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vDesc', '0')),
            vII=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vII', '0')),
            vIPI=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vIPI', '0')),
            vIPIDevol=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vIPIDevol', '0')),
            vPIS=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vPIS', '0')),
            vCOFINS=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vCOFINS', '0')),
            vOutro=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vOutro', '0')),
            vNF=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vNF', '0')),
            vTotTrib=self._safe_decimal(self._safe_findtext(icms_tot_el, 'nfe:vTotTrib', '0'))
        )

    def _criar_transporte_empresa(self, nota):
        """Cria transporte no banco da EMPRESA"""
        transp_el = self.infNFe.find('nfe:transp', namespaces=self.ns)
        if transp_el is None:
            return

        vol_el = transp_el.find('nfe:vol', namespaces=self.ns)

        TransporteFlat.objects.create(
            nota_fiscal_id=nota.id,
            modFrete=self._safe_int(self._safe_findtext(transp_el, 'nfe:modFrete', '0')),
            qVol=self._safe_int(self._safe_findtext(vol_el, 'nfe:qVol', '0')) if vol_el else None
        )

    def _criar_cobranca_empresa(self, nota):
        """Cria cobrança no banco da EMPRESA"""
        cobr_el = self.infNFe.find('nfe:cobr', namespaces=self.ns)
        if cobr_el is None:
            return CobrancaFlat.objects.create(nota_fiscal_id=nota.id)

        fat_el = cobr_el.find('nfe:fat', namespaces=self.ns)

        return CobrancaFlat.objects.create(
            nota_fiscal_id=nota.id,
            nFat=self._safe_findtext(fat_el, 'nfe:nFat') if fat_el else None,
            vOrig=self._safe_decimal(self._safe_findtext(fat_el, 'nfe:vOrig', '0')) if fat_el else None,
            vDesc=self._safe_decimal(self._safe_findtext(fat_el, 'nfe:vDesc', '0')) if fat_el else None,
            vLiq=self._safe_decimal(self._safe_findtext(fat_el, 'nfe:vLiq', '0')) if fat_el else None
        )

    def _criar_pagamento_empresa(self, cobranca):
        """Cria pagamentos no banco da EMPRESA"""
        if cobranca is None:
            return

        cobr_el = self.infNFe.find('nfe:cobr', namespaces=self.ns)
        if cobr_el is None:
            return

        for pag_el in cobr_el.findall('nfe:pag', namespaces=self.ns):
            PagamentoFlat.objects.create(
                cobranca_id=cobranca.id,
                tPag=self._safe_findtext(pag_el, 'nfe:tPag'),
                vPag=self._safe_decimal(self._safe_findtext(pag_el, 'nfe:vPag', '0'))
            )
