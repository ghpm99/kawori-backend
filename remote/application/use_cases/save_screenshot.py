class SaveScreenshotUseCase:
    def execute(
        self,
        request_files,
        media_root,
        os_path,
        os_remove_fn,
        screenshot_model,
        file_class,
        notify_screenshot_fn,
    ):
        if not request_files.get("image"):
            return {"msg": "Nao existe nenhuma imagem anexo"}, 400

        fullname = os_path.join(media_root, "screenshot/screenshot.png")
        if os_path.exists(fullname):
            os_remove_fn(fullname)

        file = request_files.get("image").file
        screenshot = screenshot_model.objects.filter(id=1).first()
        if screenshot is None:
            screenshot = screenshot_model()

        screenshot.image.save("screenshot.png", file_class(file), save=True)
        notify_screenshot_fn()
        return {"msg": "Ok"}, 200
