from rest_framework import serializers
from .models import Company, Product, Event, Lead, Contact, Cnes
from django.contrib.auth.models import User

from django.core.mail import EmailMultiAlternatives, get_connection
from django.conf import settings
import requests
from io import BytesIO


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    empresa_grupo_nome = serializers.CharField(source='empresa_grupo.nome', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'nome', 'empresa_grupo', 'empresa_grupo_nome', 'created_at']


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'


class ContactSerializer(serializers.ModelSerializer):
    # Definir o ID explicitamente permite que ele passe na validação
    # e chegue ao método update do LeadSerializer
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Contact
        fields = ['id', 'nome', 'setor', 'email', 'email_extra', 'celular']


class LeadSerializer(serializers.ModelSerializer):
    envio_email = serializers.BooleanField(write_only=True, required=False)
    origem_lp = serializers.CharField(write_only=True, required=False)

    contatos = ContactSerializer(many=True, required=False)
    empresas_grupo = serializers.PrimaryKeyRelatedField(many=True, queryset=Company.objects.all(), required=False)
    produtos_interesse = serializers.PrimaryKeyRelatedField(many=True, queryset=Product.objects.all(), required=False)

    # Campos de auditoria como objetos completos (read_only)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    deleted_by = UserSerializer(read_only=True)

    class Meta:
        model = Lead
        fields = '__all__'

    def create(self, validated_data):
        envio_email = validated_data.pop('envio_email', False)
        origem_lp = validated_data.pop('origem_lp', None)

        contatos_data = validated_data.pop('contatos', [])
        empresas_data = validated_data.pop('empresas_grupo', [])
        produtos_data = validated_data.pop('produtos_interesse', [])

        # PEGA O USUÁRIO DO CONTEXTO
        request = self.context.get('request')
        user = request.user if request and hasattr(request, 'user') else None

        # O created_by será definido automaticamente pelo AuditModel.save()
        # mas vamos garantir que o validated_data tenha o contexto
        lead = Lead.objects.create(**validated_data)

        lead.empresas_grupo.set(empresas_data)
        lead.produtos_interesse.set(produtos_data)

        for contato_data in contatos_data:
            # PASSA O USUÁRIO PARA O CONTATO
            if user and user.is_authenticated:
                contato_data['created_by'] = user
            Contact.objects.create(lead=lead, **contato_data)

        # DISPARO DE EMAIL
        if envio_email and origem_lp:
            self._enviar_email_lead(lead, origem_lp)

        return lead

    def _enviar_email_lead(self, lead, origem_lp):
        contato = lead.contatos.first()
        if not contato:
            return

        anexo_url = None
        nome_arquivo = None

        if origem_lp == "saude" and lead.cnes:
            anexo_url = f"https://numb3rs-web.s3.us-east-1.amazonaws.com/dbsaude/home/atual/{lead.cnes}.png"
            nome_arquivo = f"relatorio_{lead.cnes}.png"

        elif origem_lp == "municipio" and lead.cidade:
            anexo_url = f"https://numb3rs-web.s3.us-east-1.amazonaws.com/dbgov/home/atual/{lead.cidade}.pdf"
            nome_arquivo = f"relatorio_{lead.cidade}.pdf"

        if not anexo_url:
            return

        # Baixa o arquivo do S3
        response = requests.get(anexo_url)
        if response.status_code != 200:
            return

        arquivo = BytesIO(response.content)

        # Conexão SMTP Numb3rs
        connection = get_connection(
            backend=settings.EMAIL_NUMB3RS__BACKEND,
            host=settings.EMAIL_NUMB3RS__HOST,
            port=settings.EMAIL_NUMB3RS__PORT,
            username=settings.EMAIL_NUMB3RS__HOST_USER,
            password=settings.EMAIL__NUMB3RS_HOST_PASSWORD,
            use_tls=settings.EMAIL_NUMB3RS__USE_TLS,
        )

        subject = "Relatório Analítico - Numb3rs Gov"

        body = f"""
            Olá {contato.nome}

            Conforme solicitado, segue em anexo o relatório Numb3rs Gov, com dados analíticos de saúde voltados para a realidade do seu município.

            Entendemos que informações corretas apoiem sua equipe na tomada de decisões de forma mais estratégica e baseadas em dados.

            Em caso de dúvidas ou sugestões, conte com a gente.
            E-mail suporte: suporte@numb3rs.com.br
            Contato Comercial: (11) 98274-3176
            Contato Suporte: (11) 94125-7849
        """

        email = EmailMultiAlternatives(
            subject,
            body,
            settings.DEFAULT__NUMB3RS_FROM_EMAIL,
            [contato.email],
            connection=connection
        )

        email.attach(nome_arquivo, arquivo.read())
        email.send()

    def update(self, instance, validated_data):
        contatos_data = validated_data.pop('contatos', None)
        empresas_data = validated_data.pop('empresas_grupo', None)
        produtos_data = validated_data.pop('produtos_interesse', None)

        # PEGA O USUÁRIO ATUAL DO CONTEXTO DA REQUISIÇÃO
        request = self.context.get('request')
        user = request.user if request and hasattr(request, 'user') else None

        # Atualiza campos simples do Lead
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # DEFINE O updated_by MANUALMENTE
        if user and user.is_authenticated:
            instance.updated_by = user

        instance.save()

        # Atualiza ManyToMany (apenas se foram enviados)
        if empresas_data is not None:
            instance.empresas_grupo.set(empresas_data)
        if produtos_data is not None:
            instance.produtos_interesse.set(produtos_data)

        # Atualiza Nested Contacts
        if contatos_data is not None:
            keep_ids = []

            for c_data in contatos_data:
                if 'id' in c_data:
                    c_id = c_data.get('id')
                    if Contact.objects.filter(id=c_id, lead=instance).exists():
                        c = Contact.objects.get(id=c_id)
                        c.nome = c_data.get('nome', c.nome)
                        c.setor = c_data.get('setor', c.setor)
                        c.email = c_data.get('email', c.email)
                        c.email_extra = c_data.get('email_extra', c.email_extra)
                        c.celular = c_data.get('celular', c.celular)

                        # DEFINE O updated_by PARA O CONTATO TAMBÉM
                        if user and user.is_authenticated:
                            c.updated_by = user

                        c.save()
                        keep_ids.append(c.id)
                else:
                    # Sem ID = Novo Contato
                    # PARA NOVOS CONTATOS, DEFINE created_by
                    if user and user.is_authenticated:
                        c_data['created_by'] = user

                    new_c = Contact.objects.create(lead=instance, **c_data)
                    keep_ids.append(new_c.id)

            # Remove contatos que não vieram na lista
            instance.contatos.exclude(id__in=keep_ids).delete()

        return instance


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class CnesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cnes
        fields = '__all__'


class CnesFileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
