import json
from datetime import datetime, timedelta

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from financial.models import Invoice, Payment
from kawori.decorators import add_cors_react_dev, validate_super_user
from kawori.utils import format_date, paginate


# Create your views here.
@add_cors_react_dev
@validate_super_user
@require_GET
def get_all_invoice_view(request, user):
    req = request.GET
    filters = {}

    if req.get('status'):
        filters['status'] = req.get('status')
    if req.get('name__icontains'):
        filters['name__icontains'] = req.get('name__icontains')
    if req.get('installments'):
        filters['installments'] = req.get('installments')
    if req.get('date__gte'):
        filters['date__gte'] = format_date(
            req.get('date__gte')) or datetime(2018, 1, 1)
    if req.get('date__lte'):
        filters['date__lte'] = format_date(
            req.get('date__lte')) or datetime.now() + timedelta(days=1)

    invoices_query = Invoice.objects.filter(**filters, user=user).order_by('id')

    data = paginate(invoices_query, req.get('page'), req.get('page_size'))

    invoices = [{
        'id': invoice.id,
        'status': invoice.status,
        'name': invoice.name,
        'installments': invoice.installments,
        'value': float(invoice.value or 0),
        'value_open': float(invoice.value_open or 0),
        'value_closed': float(invoice.value_closed or 0),
        'date': invoice.date,
        'contract': invoice.contract.id,
        'tags': [{
            'id': tag.id,
            'name': tag.name,
            'color': tag.color
        } for tag in invoice.tags.all()]
    } for invoice in data.get('data')]

    data['data'] = invoices

    return JsonResponse({'data': data})


@add_cors_react_dev
@validate_super_user
@require_GET
def detail_invoice_view(request, id, user):

    invoice = Invoice.objects.filter(id=id, user=user).first()

    if (invoice is None):
        return JsonResponse({'msg': 'Invoice not found'}, status=404)

    tags = [{
        'id': tag.id,
        'name': tag.name,
        'color': tag.color
    } for tag in invoice.tags.all()]

    invoice = {
        'id': invoice.id,
        'status': invoice.status,
        'name': invoice.name,
        'installments': invoice.installments,
        'value': float(invoice.value or 0),
        'value_open': float(invoice.value_open or 0),
        'value_closed': float(invoice.value_closed or 0),
        'date': invoice.date,
        'contract': invoice.contract.id,
        'contract_name': invoice.contract.name,
        'tags': tags
    }

    return JsonResponse({'data': invoice})


@add_cors_react_dev
@validate_super_user
@require_GET
def detail_invoice_payments_view(request, id, user):
    req = request.GET
    payments_query = Payment.objects.filter(
        invoice=id, user=user).order_by('id')

    data = paginate(payments_query, req.get('page'), req.get('page_size'))

    payments = [{
        'id': payment.id,
        'status': payment.status,
        'type': payment.type,
        'name': payment.name,
        'date': payment.date,
        'installments': payment.installments,
        'payment_date': payment.payment_date,
        'fixed': payment.fixed,
        'value': float(payment.value or 0),
    } for payment in data.get('data')]

    data['data'] = payments

    return JsonResponse({'data': data})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def save_tag_invoice_view(request, id, user):

    data = json.loads(request.body)

    if (data is None):
        return JsonResponse({'msg': 'Tags not found'}, status=404)

    invoice = Invoice.objects.filter(id=id, user=user).first()
    invoice.tags.set(data)
    invoice.save()

    return JsonResponse({'msg': 'ok'})
