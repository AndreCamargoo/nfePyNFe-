from rest_framework import serializers


class TokenResponseSerializerDocumentacao(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()


class TokenRefreshResponseSerializerDocumentacao(serializers.Serializer):
    access = serializers.CharField()


class UserProfileResponseSerializerDocumentacao(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class UserProfileCreateRequestSerializerDocumentacao(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

# Serializer para o response (usuário criado)


class UserProfileCreateResponseSerializerDocumentacao(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()


class UserUpdateProfileRequestSerializerDocumentacao(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True, required=False)


class UserUpdateProfileResponseSerializerDocumentacao(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class PasswordResetRequestSerializerDocumentacao(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        help_text="E-mail do usuário para envio do link de redefinição de senha"
    )


class PasswordResetResponseSerializerDocumentacao(serializers.Serializer):
    message = serializers.CharField(
        help_text="Confirmação de que o e-mail de redefinição foi enviado"
    )


class PasswordResetErrorSerializerDocumentacao(serializers.Serializer):
    error = serializers.CharField(help_text="Mensagem de erro caso o e-mail não seja encontrado")


class PasswordResetConfirmRequestSerializerDocumentacao(serializers.Serializer):
    uidb64 = serializers.CharField(
        required=True,
        help_text="UID codificado do usuário enviado no e-mail"
    )
    token = serializers.CharField(
        required=True,
        help_text="Token de redefinição de senha enviado no e-mail"
    )
    new_password = serializers.CharField(
        required=True,
        help_text="Nova senha do usuário"
    )


class PasswordResetConfirmResponseSerializerDocumentacao(serializers.Serializer):
    message = serializers.CharField(
        help_text="Mensagem de confirmação de que a senha foi redefinida com sucesso"
    )


class PasswordResetConfirmErrorSerializerDocumentacao(serializers.Serializer):
    error = serializers.CharField(help_text="Mensagem de erro caso falhe a validação ou token expirado")
