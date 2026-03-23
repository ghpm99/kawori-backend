class SendKeyPressUseCase:
    def execute(self, payload, send_key_press_fn):
        send_key_press_fn(payload.get("keys"))
        return {"msg": "Ok"}, 200
