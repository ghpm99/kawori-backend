from django.conf import settings
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.deprecation import MiddlewareMixin


class CsrfCookieOnlyMiddleware(CsrfViewMiddleware):
    def process_request(self, request):
        """Força Django a aceitar o CSRF apenas do cookie"""
        if "csrftoken" in request.COOKIES:
            request.META["HTTP_X_CSRFTOKEN"] = request.COOKIES["csrftoken"]


class SimpleCorsMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.META.get("HTTP_ORIGIN") in settings.BASE_URL_FRONTEND_LIST:
            response["Access-Control-Allow-Origin"] = request.META.get("HTTP_ORIGIN")
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, Accept, Origin, User-Agent, Referer, Host, Connection, "
                "Access-Control-Request-Method, Access-Control-Request-Headers, Access-Control-Allow-Origin"
            )
        return response

    def process_request(self, request):
        if request.method == "OPTIONS":
            response = HttpResponse()
            if request.META.get("HTTP_ORIGIN") in settings.BASE_URL_FRONTEND_LIST:
                response["Access-Control-Allow-Origin"] = request.META.get("HTTP_ORIGIN")
                response["Access-Control-Allow-Credentials"] = "true"
                response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                response["Access-Control-Allow-Headers"] = (
                    "Authorization, Content-Type, Accept, Origin, User-Agent, Referer, Host, Connection, "
                    "Access-Control-Request-Method, Access-Control-Request-Headers, Access-Control-Allow-Origin"
                )
                return response
        return None
