from django.utils.deprecation import MiddlewareMixin

import threading
_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, 'user', None)


def set_current_user(user):
    _thread_locals.user = user


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = request.user
        response = self.get_response(request)
        return response


class CookieAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware para extrair token JWT do cookie HttpOnly
    e adicionar ao header Authorization para o DRF funcionar.
    Também autentica o usuário via JWT e define request.user e thread-local.
    """

    def process_request(self, request):
        access_token = request.COOKIES.get('access_token')

        if access_token:
            request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
            request.token_from_cookie = True

            # Resolve request.user via DRF JWT agora, para que thread-local
            # fique disponível durante o save() do AuditModel
            try:
                from rest_framework_simplejwt.authentication import JWTAuthentication
                auth = JWTAuthentication()
                result = auth.authenticate(request)
                if result is not None:
                    user, token = result
                    request.user = user
                    _thread_locals.user = user
            except Exception:
                pass
