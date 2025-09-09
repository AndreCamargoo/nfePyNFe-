from django.db import models
from empresa.models import Empresa


class NotaFiscal(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='empresa')
    chave = models.CharField(max_length=44, unique=True)
    versao = models.CharField(max_length=10)
    dhEmi = models.DateTimeField(null=True, blank=True)
    dhSaiEnt = models.DateTimeField(null=True, blank=True)
    tpAmb = models.IntegerField()
    fileXml = models.FileField(upload_to='xml/', null=True, blank=True)
    filePdf = models.FileField(upload_to='danfe/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"NF-e {self.chave}"


class Ide(models.Model):
    nota_fiscal = models.OneToOneField(NotaFiscal, on_delete=models.CASCADE, related_name='ide')
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

    def __str__(self):
        return f"Serie {self.serie}"


class Emitente(models.Model):
    nota_fiscal = models.OneToOneField(NotaFiscal, on_delete=models.CASCADE, related_name='emitente')
    CNPJ = models.CharField(max_length=14, null=True, blank=True)
    xNome = models.CharField(max_length=100, null=True, blank=True)
    xFant = models.CharField(max_length=100, blank=True, null=True)
    IE = models.CharField(max_length=20, null=True, blank=True)
    CRT = models.IntegerField()
    # Endereço simplificado
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

    def __str__(self):
        return f"{self.xNome} - {self.xFant}"


class Destinatario(models.Model):
    nota_fiscal = models.OneToOneField(NotaFiscal, on_delete=models.CASCADE, related_name='destinatario')
    CNPJ = models.CharField(max_length=14, null=True, blank=True)
    xNome = models.CharField(max_length=100, null=True, blank=True)
    IE = models.CharField(max_length=20, blank=True, null=True)
    indIEDest = models.IntegerField(null=True, blank=True)
    # Endereço simplificado
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

    def __str__(self):
        return f"{self.xNome} - {self.xMun}"


class Produto(models.Model):
    nota_fiscal = models.ForeignKey(NotaFiscal, on_delete=models.CASCADE, related_name='produtos')
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

    def __str__(self):
        return f"{self.nItem} - {self.xProd}"


class Imposto(models.Model):
    produto = models.OneToOneField(Produto, on_delete=models.CASCADE, related_name='imposto')
    vTotTrib = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # ICMS simplificado
    orig = models.CharField(max_length=1, null=True, blank=True)
    CST = models.CharField(max_length=3, null=True, blank=True)
    # Outros impostos
    vIPI = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    vPIS = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    vCOFINS = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"{self.produto} - {self.vTotTrib}"


class Total(models.Model):
    nota_fiscal = models.OneToOneField(NotaFiscal, on_delete=models.CASCADE, related_name='total')
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

    def __str__(self):
        return f"{self.vNF} - {self.vTotTrib}"


class Transporte(models.Model):
    nota_fiscal = models.OneToOneField(NotaFiscal, on_delete=models.CASCADE, related_name='transporte')
    modFrete = models.IntegerField(null=True, blank=True)
    qVol = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.modFrete} - {self.qVol}"


class Cobranca(models.Model):
    nota_fiscal = models.OneToOneField(NotaFiscal, on_delete=models.CASCADE, related_name='cobranca')
    nFat = models.CharField(max_length=20, null=True, blank=True)
    vOrig = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vDesc = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vLiq = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.nFat} - {self.vOrig}"


class Pagamento(models.Model):
    cobranca = models.ForeignKey(Cobranca, on_delete=models.CASCADE, related_name='pagamentos')
    indPag = models.IntegerField(null=True, blank=True)
    tPag = models.IntegerField(null=True, blank=True)
    vPag = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tpIntegra = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.indPag} - {self.tpIntegra}"
