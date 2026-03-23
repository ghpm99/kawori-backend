import json


class GetScreenSizeUseCase:
    def execute(self, config_model, get_object_or_404_fn):
        screen_size = get_object_or_404_fn(
            config_model, type=config_model.CONFIG_SCREEN
        )
        return json.loads(screen_size.value)
