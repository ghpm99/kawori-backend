class MouseMoveUseCase:
    def execute(self, payload, mouse_move_fn):
        mouse_move_fn(payload.get("x"), payload.get("y"))
        return {"msg": "Ok"}, 200
