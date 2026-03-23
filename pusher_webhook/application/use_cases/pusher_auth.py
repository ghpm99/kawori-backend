class PusherAuthUseCase:
    def execute(self, request, auth_fn):
        values = request.body.decode("utf-8").split("&")
        socket_id = ""
        channel_name = ""
        for value in values:
            if value.startswith("socket_id"):
                socket_id = value.split("=")[1]
            elif value.startswith("channel_name"):
                channel_name = value.split("=")[1]

        return auth_fn(request, channel_name, socket_id)
