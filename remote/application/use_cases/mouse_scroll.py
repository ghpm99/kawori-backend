class MouseScrollUseCase:
    def execute(self, payload, mouse_scroll_fn):
        mouse_scroll_fn(payload.get("value"))
        return {"msg": "Ok"}, 200
