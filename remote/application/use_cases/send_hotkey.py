class SendHotkeyUseCase:
    def execute(self, payload, send_hotkey_fn):
        send_hotkey_fn(payload.get("hotkey"))
        return {"msg": "Ok"}, 200
