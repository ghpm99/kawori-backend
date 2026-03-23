from django.http import JsonResponse
from django.views.decorators.http import require_GET

from earnings.application.use_cases.get_all_earnings import GetAllEarningsUseCase
from kawori.decorators import validate_user
from kawori.utils import boolean, format_date, paginate
from payment.models import Payment


def get_status_filter(status_params):
    if status_params == "all" or status_params == "":
        return None

    if status_params == "open" or status_params == "0":
        return Payment.STATUS_OPEN

    if status_params == "done" or status_params == "1":
        return Payment.STATUS_DONE

    return None


@require_GET
@validate_user("financial")
def get_all_view(request, user):
    return JsonResponse(
        GetAllEarningsUseCase().execute(
            request_query=request.GET,
            user=user,
            payment_model=Payment,
            paginate_fn=paginate,
            get_status_filter_fn=get_status_filter,
            format_date_fn=format_date,
            boolean_fn=boolean,
        )
    )
