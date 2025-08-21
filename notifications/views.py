import requests
import os
from rest_framework.views import APIView
from rest_framework import response, status


class SendNotificationAPIView(APIView):
    __base_url = 'https://api.callmebot.com/whatsapp.php'
    __api_key = os.getenv('CALLMEBOT_API_KEY')

    def post(self, request, *args, **kwargs):
        message = request.data.get("message")
        if not message:
            return response.Response(
                {"error": "Message é obrigatoria."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            res = requests.get(
                url=f'{self.__base_url}?phone=+5521999938712&text={message}&apikey={self.__api_key}'
            )
            return response.Response({
                "callmebot_response": res.text,
                "status_code": res.status_code
            }, status=status.HTTP_200_OK)

        except requests.RequestException as e:
            return response.Response(
                {"error": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
