from django.db import models


class NotaFiscalFlat(models.Model):
    empresa_id = models.IntegerField()
    chave = models.CharField(max_length=44, unique=True)
    versao = models.CharField(max_length=10)
    dhEmi = models.DateTimeField(null=True, blank=True)
    dhSaiEnt = models.DateTimeField(null=True, blank=True)
    tpAmb = models.IntegerField()
    fileXml = models.CharField(max_length=500, null=True, blank=True)
    filePdf = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'nfe_notafiscal_flat'
        verbose_name = 'Nota Fiscal (Flat)'
        verbose_name_plural = 'Notas Fiscais (Flat)'
        managed = True

    def __str__(self):
        return f"NF-e {self.chave}"


class IdeFlat(models.Model):
    nota_fiscal_id = models.IntegerField()
    cUF = models.CharField(max_length=2, null=True, blank=True)
    natOp = models.CharField(max_length=60, null=True, blank=True)
    mod = models.CharField(max_length=2, null=True, blank=True)
    serie = models.CharField(max_length=5, null=True, blank=True)
    nNF = models.CharField(max_length=10, null=True, blank=True)
    tpNF = models.IntegerField(null=True, blank=True)
    idDest = models.IntegerField(null=True, blank=True)
    cMunFG = models.CharField(max_length=7, null=True, blank=True)
    tpImp = models.IntegerField(null=True, blank=True)
    tpEmis = models.IntegerField(null=True, blank=True)
    cDV = models.CharField(max_length=1, null=True, blank=True)
    finNFe = models.IntegerField(null=True, blank=True)
    indFinal = models.IntegerField(null=True, blank=True)
    indPres = models.IntegerField(null=True, blank=True)
    indIntermed = models.IntegerField(null=True, blank=True)
    procEmi = models.IntegerField(null=True, blank=True)
    verProc = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'nfe_ide_flat'
        verbose_name = 'IDE (Flat)'
        verbose_name_plural = 'IDEs (Flat)'
        managed = True

    def __str__(self):
        return f"Serie {self.serie}"


class EmitenteFlat(models.Model):
    nota_fiscal_id = models.IntegerField()
    CNPJ = models.CharField(max_length=14, null=True, blank=True)
    xNome = models.CharField(max_length=100, null=True, blank=True)
    xFant = models.CharField(max_length=100, blank=True, null=True)
    IE = models.CharField(max_length=20, null=True, blank=True)
    CRT = models.IntegerField()
    xLgr = models.CharField(max_length=100, null=True, blank=True)
    nro = models.CharField(max_length=10, null=True, blank=True)
    xBairro = models.CharField(max_length=50, null=True, blank=True)
    cMun = models.CharField(max_length=7, null=True, blank=True)
    xMun = models.CharField(max_length=50, null=True, blank=True)
    UF = models.CharField(max_length=2, null=True, blank=True)
    CEP = models.CharField(max_length=8, null=True, blank=True)
    cPais = models.CharField(max_length=4, null=True, blank=True)
    xPais = models.CharField(max_length=50, null=True, blank=True)
    fone = models.CharField(max_length=15, blank=True, null=True)

    class Meta:
        db_table = 'nfe_emitente_flat'
        verbose_name = 'Emitente (Flat)'
        verbose_name_plural = 'Emitentes (Flat)'
        managed = True

    def __str__(self):
        return f"{self.xNome} - {self.xFant}"


class DestinatarioFlat(models.Model):
    nota_fiscal_id = models.IntegerField()
    CNPJ = models.CharField(max_length=14, null=True, blank=True)
    xNome = models.CharField(max_length=100, null=True, blank=True)
    IE = models.CharField(max_length=20, blank=True, null=True)
    indIEDest = models.IntegerField(null=True, blank=True)
    xLgr = models.CharField(max_length=100, null=True, blank=True)
    nro = models.CharField(max_length=10, null=True, blank=True)
    xCpl = models.CharField(max_length=50, blank=True, null=True)
    xBairro = models.CharField(max_length=50, null=True, blank=True)
    cMun = models.CharField(max_length=7, null=True, blank=True)
    xMun = models.CharField(max_length=50, null=True, blank=True)
    UF = models.CharField(max_length=2, null=True, blank=True)
    CEP = models.CharField(max_length=8, null=True, blank=True)
    cPais = models.CharField(max_length=4, null=True, blank=True)
    xPais = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'nfe_destinatario_flat'
        verbose_name = 'Destinatario (Flat)'
        verbose_name_plural = 'Destinatarios (Flat)'
        managed = True

    def __str__(self):
        return f"{self.xNome} - {self.xMun}"


class ProdutoFlat(models.Model):
    nota_fiscal_id = models.IntegerField()
    nItem = models.IntegerField()
    cProd = models.CharField(max_length=20, null=True, blank=True)
    cEAN = models.CharField(max_length=20, blank=True, null=True)
    xProd = models.CharField(max_length=200, null=True, blank=True)
    NCM = models.CharField(max_length=10, null=True, blank=True)
    CFOP = models.CharField(max_length=4, null=True, blank=True)
    uCom = models.CharField(max_length=6, null=True, blank=True)
    qCom = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    vUnCom = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    vProd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    uTrib = models.CharField(max_length=6, null=True, blank=True)
    qTrib = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    vUnTrib = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    indTot = models.IntegerField()

    class Meta:
        db_table = 'nfe_produto_flat'
        verbose_name = 'Produto (Flat)'
        verbose_name_plural = 'Produtos (Flat)'
        managed = True

    def __str__(self):
        return f"{self.nItem} - {self.xProd}"


class ImpostoFlat(models.Model):
    produto_id = models.IntegerField()
    vTotTrib = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    orig = models.CharField(max_length=1, null=True, blank=True)
    CST = models.CharField(max_length=3, null=True, blank=True)
    vIPI = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    vPIS = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    vCOFINS = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'nfe_imposto_flat'
        verbose_name = 'Imposto (Flat)'
        verbose_name_plural = 'Impostos (Flat)'
        managed = True

    def __str__(self):
        return f"Imposto - {self.vTotTrib}"


class TotalFlat(models.Model):
    nota_fiscal_id = models.IntegerField()
    vBC = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vICMS = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vICMSDeson = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vFCP = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vBCST = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vST = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vFCPST = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vFCPSTRet = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vProd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vFrete = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vSeg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vDesc = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vII = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vIPI = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vIPIDevol = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vPIS = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vCOFINS = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vOutro = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vNF = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vTotTrib = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'nfe_total_flat'
        verbose_name = 'Total (Flat)'
        verbose_name_plural = 'Totais (Flat)'
        managed = True

    def __str__(self):
        return f"Total - {self.vNF}"


class TransporteFlat(models.Model):
    nota_fiscal_id = models.IntegerField()
    modFrete = models.IntegerField(null=True, blank=True)
    qVol = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'nfe_transporte_flat'
        verbose_name = 'Transporte (Flat)'
        verbose_name_plural = 'Transportes (Flat)'
        managed = True

    def __str__(self):
        return f"Transporte - {self.modFrete}"


class CobrancaFlat(models.Model):
    nota_fiscal_id = models.IntegerField()
    nFat = models.CharField(max_length=20, null=True, blank=True)
    vOrig = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vDesc = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vLiq = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'nfe_cobranca_flat'
        verbose_name = 'Cobrança (Flat)'
        verbose_name_plural = 'Cobranças (Flat)'
        managed = True

    def __str__(self):
        return f"Cobrança - {self.nFat}"


class PagamentoFlat(models.Model):
    cobranca_id = models.IntegerField()
    indPag = models.IntegerField(null=True, blank=True)
    tPag = models.IntegerField(null=True, blank=True)
    vPag = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tpIntegra = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'nfe_pagamento_flat'
        verbose_name = 'Pagamento (Flat)'
        verbose_name_plural = 'Pagamentos (Flat)'
        managed = True

    def __str__(self):
        return f"Pagamento - {self.tPag}"
