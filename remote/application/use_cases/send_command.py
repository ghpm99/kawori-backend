class SendCommandUseCase:
    def execute(self, payload, send_command_fn):
        send_command_fn(payload.get("cmd"))
        return {"msg": "ok"}, 200
