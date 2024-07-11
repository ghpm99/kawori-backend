import json
from django.http import JsonResponse
from classification.models import Answer, AnswerSummary, Question
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
    answer_list = Answer.objects.filter(user=user).order_by('-id')

    data = [{
        'id': answer.id,
        'question': answer.question.question_text,
        'vote': answer.vote,
        'bdo_class': answer.bdo_class.abbreviation,
        'combat_style': answer.combat_style,
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

    combat_style = data.get('combat_style')
    if not combat_style:
        return JsonResponse({'msg': 'Estilo de combate não informado!'}, status=400)
    if isinstance(combat_style, int) is False:
        return JsonResponse({'msg': 'Estilo de combate invalido'}, status=400)

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
        combat_style=combat_style,
        user=user,
        vote=vote
    )

    return JsonResponse({'msg': 'Voto registrado com sucesso!'})


@add_cors_react_dev
@require_GET
def get_bdo_class(request):

    bdo_classes = BDOClass.objects.order_by('abbreviation')

    bdo_class = [{
        'id': bdo_class.id,
        'name': bdo_class.name,
        'abbreviation': bdo_class.abbreviation,
        'class_image': bdo_class.class_image.url if bdo_class.class_image else '',
        'color': bdo_class.color if bdo_class.color else ''
    } for bdo_class in bdo_classes]

    return JsonResponse({'class': bdo_class})


@add_cors_react_dev
@require_GET
def total_votes(request):
    total_votes = Answer.objects.count()

    return JsonResponse({'total_votes': total_votes})


@add_cors_react_dev
@require_GET
def answer_by_class(request):
    bdo_classes = BDOClass.objects.order_by('abbreviation')

    data = []
    for bdo_class in bdo_classes:
        answers_count = Answer.objects.filter(bdo_class=bdo_class).count()
        data.append({
            'class': bdo_class.abbreviation,
            'answers_count': answers_count,
            'color': bdo_class.color if bdo_class.color else ''
        })

    return JsonResponse({'data': data})


@add_cors_react_dev
@require_GET
def get_answer_summary(request):
    answers = AnswerSummary.objects.all()

    data = []
    for answer in answers:
        data.append({
            'id': answer.id,
            'bdo_class': answer.bdo_class.id,
            'updated_at': answer.updated_at,
            'resume': answer.resume
        })

    return JsonResponse({'data': data})
