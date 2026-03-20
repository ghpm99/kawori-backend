from django.contrib import admin

from classification.models import Answer, Path, Question


# Register your models here.
class QuestionConfig(admin.ModelAdmin):
    list_display = ("id", "question_text", "pub_date")


class AnswerConfig(admin.ModelAdmin):
    list_display = (
        "question",
        "bdo_class",
        "user",
        "created_at",
        "like_count",
        "dislike_count",
    )


class PathConfig(admin.ModelAdmin):
    list_display = ("url", "affected_class", "date_path", "created_at")


admin.site.register(Question, QuestionConfig)
admin.site.register(Answer, AnswerConfig)
admin.site.register(Path, PathConfig)
