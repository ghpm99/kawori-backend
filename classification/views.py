import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_CLASSIFICATION
from classification.application.use_cases.get_bdo_class import GetBDOClassUseCase
from classification.application.use_cases.get_all_questions import (
    GetAllQuestionsUseCase,
)
from classification.application.use_cases.get_all_answers import GetAllAnswersUseCase
from classification.application.use_cases.get_answer_summary import (
    GetAnswerSummaryUseCase,
)
from classification.application.use_cases.answer_by_class import AnswerByClassUseCase
from classification.application.use_cases.register_answer import RegisterAnswerUseCase
from classification.interfaces.api.serializers.get_all_questions_serializers import (
    GetAllQuestionsResponseSerializer,
)
from classification.interfaces.api.serializers.get_all_answers_serializers import (
    GetAllAnswersResponseSerializer,
)
from classification.interfaces.api.serializers.get_answer_summary_serializers import (
    GetAnswerSummaryResponseSerializer,
)
from classification.interfaces.api.serializers.answer_by_class_serializers import (
    AnswerByClassResponseSerializer,
)
from classification.interfaces.api.serializers.register_answer_serializers import (
    RegisterAnswerRequestSerializer,
)
from classification.interfaces.api.serializers.get_bdo_class_serializers import (
    GetBDOClassResponseSerializer,
)
from classification.interfaces.api.serializers.total_votes_serializers import (
    TotalVotesResponseSerializer,
)
from classification.application.use_cases.total_votes import TotalVotesUseCase
from classification.models import Answer, AnswerSummary, Question
from facetexture.models import BDOClass
from facetexture.views import get_bdo_class_image_url, get_bdo_class_symbol_url
from kawori.decorators import validate_user


@require_GET
@validate_user("blackdesert")
def get_all_questions(request, user):
    payload, status_code = GetAllQuestionsUseCase().execute(question_model=Question)
    serializer = GetAllQuestionsResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@validate_user("blackdesert")
def get_all_answers(request, user):
    payload, status_code = GetAllAnswersUseCase().execute(
        user=user,
        answer_model=Answer,
    )
    serializer = GetAllAnswersResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_POST
@validate_user("blackdesert")
@audit_log("answer.register", CATEGORY_CLASSIFICATION, "Answer")
def register_answer(request, user):
    data = json.loads(request.body)
    serializer = RegisterAnswerRequestSerializer(data=data)
    serializer.is_valid(raise_exception=False)

    payload, status_code = RegisterAnswerUseCase().execute(
        payload=data,
        user=user,
        question_model=Question,
        bdo_class_model=BDOClass,
        answer_model=Answer,
    )
    return JsonResponse(payload, status=status_code)


@require_GET
def get_bdo_class(request):
    payload, status_code = GetBDOClassUseCase().execute(
        bdo_class_model=BDOClass,
        get_bdo_class_image_url_fn=get_bdo_class_image_url,
        get_bdo_class_symbol_url_fn=get_bdo_class_symbol_url,
    )
    serializer = GetBDOClassResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
def total_votes(request):
    payload, status_code = TotalVotesUseCase().execute(answer_model=Answer)
    serializer = TotalVotesResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
def answer_by_class(request):
    payload, status_code = AnswerByClassUseCase().execute(
        bdo_class_model=BDOClass,
        answer_model=Answer,
    )
    serializer = AnswerByClassResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


def process_style_resume(resume):
    answer = []
    for key in resume:
        answer.append(
            {
                "text": resume[key]["question_text"],
                "details": resume[key]["question_details"],
                "avg_votes": resume[key]["avg_votes"],
                "answer": resume[key]["answer"],
            }
        )

    return answer


def process_resume(resume):
    for key in resume:
        resume[key] = process_style_resume(resume[key])
    return resume


@require_GET
def get_answer_summary(request):
    payload, status_code = GetAnswerSummaryUseCase().execute(
        answer_summary_model=AnswerSummary,
        process_resume_fn=process_resume,
    )
    serializer = GetAnswerSummaryResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)
