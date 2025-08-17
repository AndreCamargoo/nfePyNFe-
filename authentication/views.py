from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str  # Corrigido aqui
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        })


class UserProfileCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        # Validações obrigatórias
        required_fields = ['username', 'email', 'password']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return Response(
                {"error": f"Os campos obrigatórios estão faltando: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica se o e-mail já está em uso
        if User.objects.filter(email=data['email']).exists():
            return Response({"error": "Este e-mail já está em uso."}, status=status.HTTP_400_BAD_REQUEST)

        # Verifica se o username já está em uso
        if User.objects.filter(username=data['username']).exists():
            return Response({"error": "Este nome de usuário já está em uso."}, status=status.HTTP_400_BAD_REQUEST)

        # Criação do usuário
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password']
        )

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
        }, status=status.HTTP_201_CREATED)


class UserUpdateProfile(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        user = request.user

        # Verifica se o usuário é o dono do perfil
        if user.id != pk:
            return Response({"error": "Você não tem permissão para atualizar este perfil."}, status=status.HTTP_403_FORBIDDEN)

        # Checa se o usuário é superadministrador, se for, permite modificar is_staff e is_active
        is_superuser = user.is_superuser

        data = request.data

        # Atualiza apenas os campos passados na requisição
        if 'username' in data:
            if User.objects.filter(username=data['username']).exclude(id=user.id).exists():
                return Response({"error": "Este nome de usuário já está em uso."}, status=status.HTTP_400_BAD_REQUEST)
            user.username = data['username']
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
        if 'password' in data:
            user.set_password(data['password'])

        # Permitir a atualização de is_active e is_staff somente para superadministradores
        if 'is_active' in data and is_superuser:
            user.is_active = data['is_active']
        if 'is_staff' in data and is_superuser:
            user.is_staff = data['is_staff']

        user.save()
        print(f"User saved: {user.id}, {user.first_name}, {user.last_name}")

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
        }, status=status.HTTP_200_OK)


class PasswordResetRequestAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')

        # Verifica se o e-mail existe no banco de dados
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'E-mail não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)

        # Cria o token de redefinição de senha
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Envia o e-mail de notificação ao usuário
        email_subject = 'Redefinição de Senha'
        email_message = render_to_string('password_reset_email.txt', {
            'user': user,
            'uid': uid,
            'token': token,
            'url_end': settings.CURRENT_URL_FRONTEND_PASSWORD_REQUEST
        })
        send_mail(email_subject, email_message, 'noreply@example.com', [user.email])

        # Retorna apenas uma confirmação de que o e-mail foi enviado
        return Response({
            'message': 'E-mail de redefinição de senha enviado. Verifique sua caixa de entrada.'
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmAPIView(APIView):
    def post(self, request):
        uidb64 = request.data.get('uidb64')
        token = request.data.get('token')

        if not uidb64:
            return Response({'error': 'UID é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

        if not token:
            return Response({'error': 'Token é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

        # Decodifica o uid para obter o ID do usuário
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))  # Corrigido aqui
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Link de redefinição inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verifica se o token é válido
        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Token inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        # Atualiza a senha
        new_password = request.data.get('new_password')
        if not new_password:
            return Response({'error': 'Senha nova não fornecida.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({'message': 'Senha redefinida com sucesso!'}, status=status.HTTP_200_OK)
