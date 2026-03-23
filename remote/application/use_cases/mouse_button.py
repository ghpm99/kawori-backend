class MouseButtonUseCase:
    def execute(self, payload, mouse_button_fn):
        mouse_button_fn(payload.get("button"))
        return {"msg": "Ok"}, 200
