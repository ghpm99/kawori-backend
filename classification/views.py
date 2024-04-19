import json
from django.http import JsonResponse
from classification.models import Answer, Question
from kawori.decorators import add_cors_react_dev, validate_user
from django.views.decorators.http import require_GET, require_POST


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


@add_cors_react_dev
@validate_user
@require_GET
def get_all_answers(request, user):
    answer_list = Answer.objects.filter(user=user)

    data = [{
        'id': answer.id,
        'question': answer.question,
        'bdo_class': answer.bdo_class,
        'created_at': answer.created_at,
    } for answer in answer_list]

    return JsonResponse({'data': data})


@add_cors_react_dev
@validate_user
@require_POST
def register_answer(request, user):
    data = json.loads(request.body)

    return JsonResponse({'msg': 'Voto registrado com sucesso!'})
