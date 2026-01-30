from rest_framework import serializers
from .models import Company, Product, Event, Lead, Contact
from django.contrib.auth.models import User


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
        fields = ['id', 'nome', 'setor', 'email', 'celular']


class LeadSerializer(serializers.ModelSerializer):
    contatos = ContactSerializer(many=True, required=False)
    empresas_grupo = serializers.PrimaryKeyRelatedField(many=True, queryset=Company.objects.all(), required=False)
    produtos_interesse = serializers.PrimaryKeyRelatedField(many=True, queryset=Product.objects.all(), required=False)

    class Meta:
        model = Lead
        fields = '__all__'

    def create(self, validated_data):
        contatos_data = validated_data.pop('contatos', [])
        empresas_data = validated_data.pop('empresas_grupo', [])
        produtos_data = validated_data.pop('produtos_interesse', [])

        lead = Lead.objects.create(**validated_data)

        lead.empresas_grupo.set(empresas_data)
        lead.produtos_interesse.set(produtos_data)

        for contato_data in contatos_data:
            Contact.objects.create(lead=lead, **contato_data)

        return lead

    def update(self, instance, validated_data):
        # Usamos .pop(..., None) para diferenciar entre "campo vazio" e "campo não enviado"
        # Isso evita apagar contatos se o campo não vier no payload (ex: PATCH parcial)
        contatos_data = validated_data.pop('contatos', None)
        empresas_data = validated_data.pop('empresas_grupo', None)
        produtos_data = validated_data.pop('produtos_interesse', None)

        # Atualiza campos simples do Lead
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
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
                # Agora o 'id' estará presente aqui porque o definimos no ContactSerializer
                if 'id' in c_data:
                    c_id = c_data.get('id')
                    # Verifica se o contato realmente pertence a este lead (Segurança)
                    if Contact.objects.filter(id=c_id, lead=instance).exists():
                        c = Contact.objects.get(id=c_id)
                        c.nome = c_data.get('nome', c.nome)
                        c.setor = c_data.get('setor', c.setor)
                        c.email = c_data.get('email', c.email)
                        c.celular = c_data.get('celular', c.celular)
                        c.save()
                        keep_ids.append(c.id)
                    else:
                        # Se vier ID inválido ou de outro lead, ignoramos ou tratamos como erro
                        pass
                else:
                    # Sem ID = Novo Contato
                    new_c = Contact.objects.create(lead=instance, **c_data)
                    keep_ids.append(new_c.id)

            # Remove contatos que não vieram na lista (Exclusão)
            # Isso é importante: se você deletou no front, essa linha deleta no banco
            instance.contatos.exclude(id__in=keep_ids).delete()

        return instance


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
