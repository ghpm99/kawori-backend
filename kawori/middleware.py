from django.middleware.csrf import CsrfViewMiddleware

class CsrfCookieOnlyMiddleware(CsrfViewMiddleware):
    def process_request(self, request):
        """Força Django a aceitar o CSRF apenas do cookie"""
        if "csrftoken" in request.COOKIES:
            request.META["HTTP_X_CSRFTOKEN"] = request.COOKIES["csrftoken"]