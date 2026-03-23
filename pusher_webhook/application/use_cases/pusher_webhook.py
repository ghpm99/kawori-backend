class PusherWebhookUseCase:
    def execute(self, request, webhook_fn):
        return webhook_fn(request)
