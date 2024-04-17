from django.http import JsonResponse
from classification.models import Question
from kawori.decorators import add_cors_react_dev, validate_user
from django.views.decorators.http import require_GET


@add_cors_react_dev
@validate_user
@require_GET
def get_all_questions(request, user):
    question_list = Question.objects.all()

    data = [{
        'id': question.id,
        'question_text': question.question_text,
        'pub_date': question.pub_date
    } for question in question_list]

    return JsonResponse({'data': data})
