from django.utils.deprecation import MiddlewareMixin

import threading
_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, 'user', None)


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
    e adicionar ao header Authorization para o DRF funcionar
    """

    def process_request(self, request):
        # Extrair token do cookie
        access_token = request.COOKIES.get('access_token')

        if access_token:
            # Adicionar ao header Authorization para o DRF funcionar
            request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
            # Opcional: adicionar um atributo ao request para saber que veio do cookie
            request.token_from_cookie = True
