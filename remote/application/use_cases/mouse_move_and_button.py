class MouseMoveAndButtonUseCase:
    def execute(self, payload, mouse_move_button_fn):
        mouse_move_button_fn(payload.get("x"), payload.get("y"), payload.get("button"))
        return {"msg": "Ok"}, 200
