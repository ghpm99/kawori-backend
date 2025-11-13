from http import HTTPStatus
from urllib.parse import urlparse
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


class OriginFilterMiddleware(MiddlewareMixin):
    def _normalize(self, value: str) -> str:
        if not value:
            return ""
        if "://" not in value:
            value = "http://" + value
        p = urlparse(value)
        return f"{p.scheme}://{p.netloc}".rstrip("/")

    def process_request(self, request):
        # Ignore preflight — SimpleCorsMiddleware já responde a OPTIONS
        if request.method == "OPTIONS":
            return None

        origin_header = request.META.get("HTTP_ORIGIN")
        # fallback para host (inclui porta quando presente)
        host_fallback = request.get_host()
        origin = origin_header or host_fallback

        origin_norm = self._normalize(origin)

        allowed = {self._normalize(settings.BASE_URL)}
        allowed.update({self._normalize(o) for o in getattr(settings, "BASE_URL_FRONTEND_LIST", [])})

        # Se origin estiver na lista de permitidos, permite.
        if origin_norm in allowed:
            return None

        return HttpResponse("Origin not allowed", status=HTTPStatus.FORBIDDEN)
