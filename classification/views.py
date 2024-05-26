import json
from django.http import JsonResponse
from classification.models import Answer, Question
from facetexture.models import BDOClass
from kawori.decorators import add_cors_react_dev, validate_user
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt


@add_cors_react_dev
@validate_user
@require_GET
def get_all_questions(request, user):
    question_list = Question.objects.order_by('id')

    data = [{
        'id': question.id,
        'question_text': question.question_text,
        'question_details': question.question_details,
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


@csrf_exempt
@add_cors_react_dev
@validate_user
@require_POST
def register_answer(request, user):
    data = json.loads(request.body)

    question_id = data.get('question_id')
    if not question_id:
        return JsonResponse({'msg': 'ID da questão não informado!'}, status=400)

    question = Question.objects.get(id=question_id)
    if not question:
        return JsonResponse({'msg': 'Questão não encontrada!'}, status=404)

    bdo_class_id = data.get('bdo_class_id')
    if not bdo_class_id:
        return JsonResponse({'msg': 'ID da classe não informado!'}, status=400)

    bdo_class = BDOClass.objects.get(id=bdo_class_id)
    if not bdo_class:
        return JsonResponse({'msg': 'Classe não encontrada!'}, status=404)

    vote = data.get('vote')
    if not vote:
        return JsonResponse({'msg': 'Voto não informado!'}, status=400)
    if isinstance(vote, int) is False:
        return JsonResponse({'msg': 'Voto deve ser um número inteiro!'}, status=400)

    Answer.objects.create(
        question_id=question_id,
        bdo_class_id=bdo_class_id,
        user=user,
        vote=vote
    )

    return JsonResponse({'msg': 'Voto registrado com sucesso!'})
