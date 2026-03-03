from rest_framework import serializers
from .models import Company, Product, Event, Lead, Contact, Cnes
from django.contrib.auth.models import User

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection, EmailMessage
import requests
from io import BytesIO

import logging
logger = logging.getLogger(__name__)


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

        # Pega o usuário do contexto da requisição
        request = self.context.get('request')
        user = request.user if request and hasattr(request, 'user') else None

        # Cria o Lead
        lead = Lead.objects.create(**validated_data)

        # Define ManyToMany
        lead.empresas_grupo.set(empresas_data)
        lead.produtos_interesse.set(produtos_data)

        # Cria contatos
        for contato_data in contatos_data:
            if user and user.is_authenticated:
                contato_data['created_by'] = user
            Contact.objects.create(lead=lead, **contato_data)

        # 🔹 Disparo de email apenas se marcado e origem_lp definido
        if envio_email and origem_lp and contatos_data:
            # Pega apenas o primeiro contato
            primeiro_contato = contatos_data[0]
            self._enviar_email_lead(lead, origem_lp, primeiro_contato)

        return lead

    def _enviar_email_lead(self, lead, origem_lp, contato_data):
        nome = contato_data.get('nome')
        email_destino = contato_data.get('email')

        # 🔹 Cria a conexão SMTP apenas uma vez
        connection = get_connection(
            backend=settings.EMAIL_NUMB3RS_BACKEND,
            host=settings.EMAIL_NUMB3RS_HOST,
            port=settings.EMAIL_NUMB3RS_PORT,
            username=settings.EMAIL_NUMB3RS_HOST_USER,
            password=settings.EMAIL_NUMB3RS_HOST_PASSWORD,
            use_tls=settings.EMAIL_NUMB3RS_USE_TLS,
        )

        if not email_destino:
            logger.warning(f"Lead {lead.id} sem email. Email não enviado.")
            return

        # Define URL e nome do arquivo
        anexo_url = None
        nome_arquivo = None
        if origem_lp == "saude" and lead.cnes:
            anexo_url = f"https://numb3rs-web.s3.us-east-1.amazonaws.com/dbsaude/home/atual/{lead.cnes}.png"
            nome_arquivo = f"relatorio_{lead.cnes}.png"
        elif origem_lp == "municipio" and lead.cidade:
            anexo_url = f"https://numb3rs-web.s3.us-east-1.amazonaws.com/dbgov/home/atual/{lead.cidade}.pdf"
            nome_arquivo = f"relatorio_{lead.cidade}.pdf"

        if not anexo_url:
            logger.warning(f"Lead {lead.id} sem anexo válido.")
            return

        try:
            # Tenta baixar o arquivo
            response = requests.get(anexo_url, timeout=10)
            response.raise_for_status()  # dispara exceção se não 200
            arquivo = BytesIO(response.content)

        except Exception as e:
            logger.error(f"Arquivo S3 não encontrado para Lead {lead.id}: {str(e)}")
            # 🔹 Email interno usando a mesma conexão
            try:
                assunto = f"[URGENTE] Falha no envio de relatório - Lead {lead.id}"
                corpo = f"""
                Não foi possível enviar o relatório para o cliente {lead.empresa} (Lead {lead.id}).
                Motivo: arquivo S3 não encontrado ou erro ao baixar.
                Tentativa de arquivo: {anexo_url}
                """
                email_interno = EmailMessage(
                    subject=assunto,
                    body=corpo,
                    from_email=settings.DEFAULT_NUMB3RS_FROM_EMAIL,
                    to=["andre.camargo@msn.com"],
                    connection=connection  # usa a mesma conexão
                )
                email_interno.send(fail_silently=False)  # força exceção se falhar
                logger.info(f"Email interno de falha enviado para andre.camargo@msn.com (Lead {lead.id})")
            except Exception as e2:
                logger.error(f"Erro ao enviar email interno de aviso de falha S3: {str(e2)}")
            return  # cancela envio para o cliente

        # Se chegou aqui, arquivo está ok, envia para o cliente
        try:
            subject = "Relatório Analítico - Numb3rs Gov"
            body = f"""
            Olá {nome},

            Conforme solicitado, segue em anexo o relatório Numb3rs Gov.

            Em caso de dúvidas:
            suporte@numb3rs.com.br
            (11) 98274-3176
            """

            email = EmailMultiAlternatives(
                subject,
                body,
                settings.DEFAULT_NUMB3RS_FROM_EMAIL,
                [email_destino],
                connection=connection
            )
            email.attach(nome_arquivo, arquivo.read())
            email.send(fail_silently=False)

            logger.info(f"Email enviado com sucesso para {email_destino} (Lead {lead.id})")

        except Exception as e:
            logger.error(f"Erro ao enviar email do Lead {lead.id} para {email_destino}: {str(e)}")

    def update(self, instance, validated_data):
        contatos_data = validated_data.pop('contatos', None)
        empresas_data = validated_data.pop('empresas_grupo', None)
        produtos_data = validated_data.pop('produtos_interesse', None)

        request = self.context.get('request')
        user = request.user if request and hasattr(request, 'user') else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if user and user.is_authenticated:
            instance.updated_by = user
        instance.save()

        if empresas_data is not None:
            instance.empresas_grupo.set(empresas_data)
        if produtos_data is not None:
            instance.produtos_interesse.set(produtos_data)

        if contatos_data is not None:
            keep_ids = []
            for c_data in contatos_data:
                if 'id' in c_data:
                    c_id = c_data['id']
                    c = Contact.objects.get(id=c_id, lead=instance)
                    c.nome = c_data.get('nome', c.nome)
                    c.setor = c_data.get('setor', c.setor)
                    c.email = c_data.get('email', c.email)
                    c.email_extra = c_data.get('email_extra', c.email_extra)
                    c.celular = c_data.get('celular', c.celular)
                    if user and user.is_authenticated:
                        c.updated_by = user
                    c.save()
                    keep_ids.append(c.id)
                else:
                    if user and user.is_authenticated:
                        c_data['created_by'] = user
                    new_c = Contact.objects.create(lead=instance, **c_data)
                    keep_ids.append(new_c.id)
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
