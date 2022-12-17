import json
import math
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from kawori.decorators import add_cors_react_dev, validate_super_user
from kawori.utils import boolean, format_date, paginate

from financial.models import Contract, Invoice, Payment, Tag
from financial.utils import calculate_installments, generate_payments, update_contract_value


@add_cors_react_dev
@validate_super_user
@require_GET
def get_all_view(request, user):

    req = request.GET
    filters = {}

    if req.get('status'):
        filters['status'] = req.get('status')
    if req.get('type'):
        filters['type'] = req.get('type')
    if req.get('name__icontains'):
        filters['name__icontains'] = req.get('name__icontains')
    if req.get('date__gte'):
        filters['date__gte'] = format_date(
            req.get('date__gte')) or datetime(2018, 1, 1)
    if req.get('date__lte'):
        filters['date__lte'] = format_date(
            req.get('date__lte')) or datetime.now() + timedelta(days=1)
    if req.get('installments'):
        filters['installments'] = req.get('installments')
    if req.get('payment_date__gte'):
        filters['payment_date__gte'] = format_date(
            req.get('payment_date__gte')) or datetime(2018, 1, 1)
    if req.get('payment_date__lte'):
        filters['payment_date__lte'] = format_date(
            req.get('payment_date__lte')) or datetime.now() + timedelta(days=1)
    if req.get('fixed'):
        filters['fixed'] = boolean(req.get('fixed'))
    if req.get('active'):
        filters['active'] = boolean(req.get('active'))

    payments_query = Payment.objects.filter(
        **filters, user=user).order_by('payment_date')

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
        'value': float(payment.value or 0)
    } for payment in data.get('data')]

    data['data'] = payments

    return JsonResponse({'data': data})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def save_new_view(request, user):

    data = json.loads(request.body)

    installments = data.get('installments')
    payment_date = data.get('payment_date')

    value_installments = calculate_installments(
        data.get('value'), installments)

    date_format = '%Y-%m-%d'

    for i in range(installments):
        payment = Payment(
            type=data.get('type'),
            name=data.get('name'),
            date=data.get('date'),
            installments=i + 1,
            payment_date=payment_date,
            fixed=data.get('fixed'),
            value=value_installments[i],
            user=user
        )
        payment.save()
        date_obj = datetime.strptime(payment_date, date_format)
        future_payment = date_obj + relativedelta(months=1)
        payment_date = future_payment.strftime(date_format)

    return JsonResponse({'msg': 'Pagamento incluso com sucesso'})


@add_cors_react_dev
@validate_super_user
@require_GET
def detail_view(request, id, user):

    data = Payment.objects.filter(id=id, user=user).first()

    if (data is None):
        return JsonResponse({'msg': 'Payment not found'}, status=404)

    payment = {
        'id': data.id,
        'status': data.status,
        'type': data.type,
        'name': data.name,
        'date': data.date,
        'installments': data.installments,
        'payment_date': data.payment_date,
        'fixed': data.fixed,
        'active': data.active,
        'value': float(data.value or 0),
        'invoice': data.invoice.id,
        'invoice_name': data.invoice.name,
        'contract': data.invoice.contract.id,
        'contract_name': data.invoice.contract.name
    }

    return JsonResponse({'data': payment})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def save_detail_view(request, id, user):

    data = json.loads(request.body)
    payment = Payment.objects.filter(id=id, user=user).first()

    if data is None:
        return JsonResponse({'msg': 'Payment not found'}, status=404)

    if payment.status == Payment.STATUS_DONE:
        return JsonResponse({'msg': 'Pagamento ja foi baixado'}, status=500)

    if data.get('type'):
        payment.type = data.get('type')
    if data.get('name'):
        payment.name = data.get('name')
    if data.get('payment_date'):
        payment.payment_date = data.get('payment_date')
    if data.get('fixed'):
        payment.fixed = data.get('fixed')
    if data.get('active'):
        payment.active = data.get('active')
    if data.get('value'):
        old_value = payment.value
        new_value = data.get('value')

        invoice_value = float(payment.invoice.value_open - old_value) + new_value
        payment.invoice.value_open = invoice_value
        payment.invoice.save()

        contract_value = float(
            payment.invoice.contract.value_open - old_value) + new_value
        payment.invoice.contract.value_open = contract_value
        payment.invoice.contract.save()

        payment.value = new_value

    payment.save()

    return JsonResponse({'msg': 'ok'})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def payoff_detail_view(request, id, user):

    payment = Payment.objects.filter(id=id, user=user).first()

    if payment.status == 1:
        return JsonResponse({'msg': 'Pagamento ja baixado'}, status=400)

    date_format = '%Y-%m-%d'

    if payment.invoice.fixed is True:
        future_payment = payment.payment_date + relativedelta(months=1)
        payment_date = future_payment.strftime(date_format)
        new_invoice = Invoice(
            type=payment.type,
            name=payment.name,
            date=payment.date,
            installments=payment.installments,
            payment_date=payment_date,
            fixed=payment.fixed,
            value=payment.value,
            value_open=payment.value,
            contract=payment.invoice.contract,
            user=user
        )
        new_invoice.save()
        tags = [tag.id for tag in payment.invoice.tags.all()]
        new_invoice.tags.set(tags)
        generate_payments(new_invoice)

        new_invoice.contract.value_open = (new_invoice.contract.value_open or 0) + new_invoice.value
        new_invoice.contract.value = (new_invoice.contract.value or 0) + new_invoice.value
        new_invoice.contract.save()


    payment.status = Payment.STATUS_DONE
    payment.save()

    payment.invoice.value_open = (payment.invoice.value_open or 0) - payment.value
    payment.invoice.value_closed = (payment.invoice.value_closed or 0) + payment.value
    payment.invoice.save()

    payment.invoice.contract.value_open = (payment.invoice.contract.value_open or 0) - payment.value
    payment.invoice.contract.value_closed = (payment.invoice.contract.value_closed or 0) + payment.value
    payment.invoice.contract.save()

    return JsonResponse({'msg': 'Pagamento baixado'})


@add_cors_react_dev
@validate_super_user
@require_GET
def report_payment_view(request, user):

    date_referrer = datetime.now().date()

    end = date_referrer + relativedelta(months=12, day=1)
    begin = date_referrer.replace(day=1) - relativedelta(months=3)

    query_fixed_debit = """
        SELECT
            SUM(value) as fixed_debit_total
        FROM
            financial_payment AS fixed_debit
        WHERE 1=1
            AND user_id=%(user_id)s
            AND type=1
            AND status=0
            AND active=true
            AND fixed=true;
    """

    with connection.cursor() as cursor:
        cursor.execute(query_fixed_debit, {'user_id': user.id})
        fixed_debit = cursor.fetchone()

    query_fixed_credit = """
        SELECT
            SUM(value) as fixed_credit_total
        FROM
            financial_payment AS fixed_credit
        WHERE 1=1
            AND user_id=%(user_id)s
            AND type=0
            AND status=0
            AND active=true
            AND fixed=true;
    """

    with connection.cursor() as cursor:
        cursor.execute(query_fixed_credit, {'user_id': user.id})
        fixed_credit = cursor.fetchone()

    queryOpen = """
        WITH debit AS (
            SELECT
                SUM(value) as debit_total,
                date_part('year', debit.payment_date) as debit_year,
                date_part('month', debit.payment_date) as debit_month
            FROM
                financial_payment AS debit
            WHERE 1=1
                AND type=1
                AND status=0
                AND active=true
                AND fixed=false
                AND user_id=%(user_id)s
                AND payment_date BETWEEN %(begin)s AND %(end)s
            GROUP BY
                date_part('year', debit.payment_date),
                date_part('month', debit.payment_date)
            ORDER BY
                date_part('year', debit.payment_date),
                date_part('month', debit.payment_date)
        ),
        credit AS (
            SELECT
                SUM(value) as credit_total,
                date_part('year', credit.payment_date) as credit_year,
                date_part('month', credit.payment_date) as credit_month
            FROM
                financial_payment AS credit
            WHERE 1=1
                AND type=0
                AND status=0
                AND active=true
                AND fixed=false
                AND user_id=%(user_id)s
                AND payment_date BETWEEN %(begin)s AND %(end)s
            GROUP BY
                date_part('year', credit.payment_date),
                date_part('month', credit.payment_date)
            ORDER BY
                date_part('year', credit.payment_date),
                date_part('month', credit.payment_date)
        ),
        fixed_debit AS (
            SELECT
                SUM(value) as fixed_debit_total,
                date_part('year', fixed_debit.payment_date) as fixed_debit_year,
                date_part('month', fixed_debit.payment_date) as fixed_debit_month
            FROM
                financial_payment AS fixed_debit
            WHERE 1=1
                AND type=1
                AND status=0
                AND active=true
                AND fixed=true
                AND user_id=%(user_id)s
                AND payment_date BETWEEN %(begin)s AND %(end)s
            GROUP BY
                date_part('year', fixed_debit.payment_date),
                date_part('month', fixed_debit.payment_date)
            ORDER BY
                date_part('year', fixed_debit.payment_date),
                date_part('month', fixed_debit.payment_date)
        ),
        fixed_credit AS (
            SELECT
                SUM(value) as fixed_credit_total,
                date_part('year', fixed_credit.payment_date) as fixed_credit_year,
                date_part('month', fixed_credit.payment_date) as fixed_credit_month
            FROM
                financial_payment AS fixed_credit
            WHERE 1=1
                AND type=0
                AND status=0
                AND active=true
                AND fixed=true
                AND user_id=%(user_id)s
                AND payment_date BETWEEN %(begin)s AND %(end)s
            GROUP BY
                date_part('year', fixed_credit.payment_date),
                date_part('month', fixed_credit.payment_date)
            ORDER BY
                date_part('year', fixed_credit.payment_date),
                date_part('month', fixed_credit.payment_date)
        )
        SELECT
            date_part('month', payment.payment_date) AS payment_month,
            date_part('year', payment.payment_date) AS payment_year,
            debit.debit_total as debit_total,
            credit.credit_total as credit_total,
            fixed_debit.fixed_debit_total as fixed_debit_open,
            fixed_credit.fixed_credit_total as fixed_credit_open
        FROM
            financial_payment AS payment
        LEFT JOIN
            debit
            ON
                debit.debit_year = date_part('year', payment.payment_date)
            AND
                debit.debit_month = date_part('month', payment.payment_date)
        LEFT JOIN
            credit
            ON
                credit.credit_year = date_part('year', payment.payment_date)
            AND
                credit.credit_month = date_part('month', payment.payment_date)
        LEFT JOIN
            fixed_debit
            ON
                fixed_debit.fixed_debit_year = date_part('year', payment.payment_date)
            AND
                fixed_debit.fixed_debit_month = date_part('month', payment.payment_date)
        LEFT JOIN
            fixed_credit
            ON
                fixed_credit.fixed_credit_year = date_part('year', payment.payment_date)
            AND
                fixed_credit.fixed_credit_month = date_part('month', payment.payment_date)
        WHERE 1=1
            AND status=0
            AND active=true
            AND user_id=%(user_id)s
            AND payment_date BETWEEN %(begin)s AND %(end)s
        GROUP BY
            date_part('year', payment.payment_date),
            date_part('month', payment.payment_date),
            debit_total,
            credit_total,
            fixed_debit_total,
            fixed_credit_total
        ORDER BY payment_year, payment_month;
        """

    with connection.cursor() as cursor:
        cursor.execute(queryOpen, {
            'user_id': user.id,
            'begin': begin,
            'end': end
        })
        datas_open = cursor.fetchall()

    open = [{
        'label': str(math.trunc(data[0])) + '/' + str(math.trunc(data[1])),
        'debit': float(data[2] or 0),
        'credit': float(data[3] or 0),
        'fixed_debit_open': float(data[4] or 0),
        'fixed_credit_open': float(data[5] or 0)
    } for data in datas_open]

    query_closed = """
        WITH debit AS (
            SELECT
                SUM(value) as debit_total,
                date_part('year', debit.payment_date) as debit_year,
                date_part('month', debit.payment_date) as debit_month
            FROM
                financial_payment AS debit
            WHERE 1=1
                AND type=1
                AND status=1
                AND active=true
                AND user_id=%(user_id)s
                AND payment_date BETWEEN %(begin)s AND %(end)s
            GROUP BY
                date_part('year', debit.payment_date),
                date_part('month', debit.payment_date)
            ORDER BY
                date_part('year', debit.payment_date),
                date_part('month', debit.payment_date)
        ),
        credit AS (
            SELECT
                SUM(value) as credit_total,
                date_part('year', credit.payment_date) as credit_year,
                date_part('month', credit.payment_date) as credit_month
            FROM
                financial_payment AS credit
            WHERE 1=1
                AND type=0
                AND status=1
                AND active=true
                AND user_id=%(user_id)s
                AND payment_date BETWEEN %(begin)s AND %(end)s
            GROUP BY
                date_part('year', credit.payment_date),
                date_part('month', credit.payment_date)
            ORDER BY
                date_part('year', credit.payment_date),
                date_part('month', credit.payment_date)
        )
        SELECT
            date_part('month', payment.payment_date) AS payment_month,
            date_part('year', payment.payment_date) AS payment_year,
            debit.debit_total as debit_total,
            credit.credit_total as credit_total
        FROM
            financial_payment AS payment
        LEFT JOIN
            debit
            ON
                debit.debit_year = date_part('year', payment.payment_date)
            AND
                debit.debit_month = date_part('month', payment.payment_date)
        LEFT JOIN
            credit
            ON
                credit.credit_year = date_part('year', payment.payment_date)
            AND
                credit.credit_month = date_part('month', payment.payment_date)
        WHERE 1=1
            AND status=1
            AND active=true
            AND user_id=%(user_id)s
            AND payment_date BETWEEN %(begin)s AND %(end)s
        GROUP BY
            date_part('year', payment.payment_date),
            date_part('month', payment.payment_date),
            debit_total,
            credit_total
        ORDER BY payment_year, payment_month;
        """

    with connection.cursor() as cursor:
        cursor.execute(query_closed, {
            'user_id': user.id,
            'begin': begin,
            'end': end
        })
        datas_closed = cursor.fetchall()

    closed = [{
        'label': str(math.trunc(data[0])) + '/' + str(math.trunc(data[1])),
        'debit': float(data[2] or 0),
        'credit': float(data[3] or 0)
    } for data in datas_closed]

    return JsonResponse({
        'data': {
            'open': open,
            'closed': closed,
            'fixed_debit': float(fixed_debit[0] or 0),
            'fixed_credit': float(fixed_credit[0] or 0)
        }
    })


@add_cors_react_dev
@validate_super_user
@require_GET
def get_all_contract_view(request, user):
    req = request.GET
    filters = {}

    if req.get('id'):
        filters['id'] = req.get('id')

    contracts_query = Contract.objects.filter(**filters, user=user).order_by('id')

    data = paginate(contracts_query, req.get('page'), req.get('page_size'))

    contracts = [{
        'id': contract.id,
        'name': contract.name,
        'value': float(contract.value or 0),
        'value_open': float(contract.value_open or 0),
        'value_closed': float(contract.value_closed or 0)
    } for contract in data.get('data')]

    data['data'] = contracts

    return JsonResponse({'data': data})


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


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def save_new_contract_view(request, user):
    data = json.loads(request.body)
    contract = Contract(
        name=data.get('name'),
        user=user
    )
    contract.save()

    return JsonResponse({'msg': 'Contrato incluso com sucesso'})


@add_cors_react_dev
@validate_super_user
@require_GET
def detail_contract_view(request, id, user):

    data = Contract.objects.filter(id=id).first()

    if (data is None):
        return JsonResponse({'msg': 'Contract not found'}, status=404)

    contract = {
        'id': data.id,
        'name': data.name,
        'value': float(data.value or 0),
        'value_open': float(data.value_open or 0),
        'value_closed': float(data.value_closed or 0)
    }

    return JsonResponse({'data': contract})


@add_cors_react_dev
@validate_super_user
@require_GET
def detail_contract_invoices_view(request, id, user):
    req = request.GET

    invoices_query = Invoice.objects.filter(contract=id, user=user).order_by('id')

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
        'tags': [{
            'id': tag.id,
            'name': tag.name,
            'color': tag.color
        } for tag in invoice.tags.all()]
    } for invoice in data.get('data')]

    data['data'] = invoices

    return JsonResponse({'data': data})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def include_new_invoice_view(request, id, user):
    data = json.loads(request.body)

    contract = Contract.objects.filter(id=id, user=user).first()
    if contract is None:
        return JsonResponse({'msg': 'Contract not found'}, status=404)

    invoice = Invoice(
        status=data.get('status'),
        type=data.get('type'),
        name=data.get('name'),
        date=data.get('date'),
        installments=data.get('installments'),
        payment_date=data.get('payment_date'),
        fixed=data.get('fixed'),
        active=data.get('active'),
        value=data.get('value'),
        value_open=data.get('value'),
        contract=contract,
        user=user
    )
    invoice.save()
    if data.get('tags'):
        invoice.tags.set(data.get('tags'))

    generate_payments(invoice)

    contract.value_open = float(contract.value_open or 0) + float(invoice.value)
    contract.value = float(contract.value or 0) + float(invoice.value)
    contract.save()

    return JsonResponse({'msg': 'Nota inclusa com sucesso'})


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
def merge_contract_view(request, id, user):
    data = json.loads(request.body)

    contract = Contract.objects.filter(id=id, user=user).first()
    if contract is None:
        return JsonResponse({'msg': 'Contract not found'}, status=404)
    contracts = data.get('contracts')

    for id in contracts:
        invoices = Invoice.objects.filter(contract=id, user=user).all()
        for invoice in invoices:
            invoice.contract = contract
            invoice.save()
        Contract.objects.filter(id=id).delete()

    update_contract_value(contract)

    return JsonResponse({'msg': 'Contratos mesclados com sucesso!'})


@add_cors_react_dev
@validate_super_user
@require_GET
def get_all_tag_view(request, user):
    req = request.GET
    filters = {}

    if req.get('name__icontains'):
        filters['name__icontains'] = req.get('name__icontains')

    datas = Tag.objects.filter(**filters, user=user).all().order_by('id')

    tags = [{
        'id': data.id,
        'name': data.name,
        'color': data.color
    } for data in datas]

    return JsonResponse({'data': tags})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def include_new_tag_view(request, user):
    data = json.loads(request.body)

    tag = Tag(
        name=data.get('name'),
        color=data.get('color'),
        user=user
    )

    tag.save()

    return JsonResponse({'msg': 'Tag inclusa com sucesso'})


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


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def update_all_contracts_value(request, user):
    contracts = Contract.objects.all()
    for contract in contracts:
        update_contract_value(contract)
    return JsonResponse({'msg': 'ok'})


@add_cors_react_dev
@validate_super_user
@require_GET
def report_count_payment_view(request, user):

    date_referrer = datetime.now().date()

    end = date_referrer + relativedelta(months=1, day=1)
    begin = date_referrer.replace(day=1)

    params = {
        'begin': begin,
        'end': end,
    }

    count_payment = """
        SELECT
            COALESCE(COUNT(id), 0) as payment_total
        FROM
            financial_payment fp
        WHERE 1=1
            AND user_id=%(user_id)s
            AND type=1
            AND active=true
            AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
    """

    with connection.cursor() as cursor:
        cursor.execute(count_payment, {**params, 'user_id': user.id})
        payment_total = cursor.fetchone()

    return JsonResponse({'data': payment_total})


@add_cors_react_dev
@validate_super_user
@require_GET
def report_amount_payment_view(request, user):
    date_referrer = datetime.now().date()

    end = date_referrer + relativedelta(months=1, day=1)
    begin = date_referrer.replace(day=1)

    params = {
        'begin': begin,
        'end': end,
    }

    count_payment = """
        SELECT
            COALESCE(SUM(value), 0) as amount_payment_total
        FROM
            financial_payment fp
        WHERE 1=1
            AND fp.user_id=%(user_id)s
            AND fp.type=1
            AND fp.active=true
            AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
    """

    with connection.cursor() as cursor:
        cursor.execute(count_payment, {**params, 'user_id': user.id})
        amount_payment_total = cursor.fetchone()

    return JsonResponse({'data': amount_payment_total})


@add_cors_react_dev
@validate_super_user
@require_GET
def report_amount_payment_open_view(request, user):
    date_referrer = datetime.now().date()

    end = date_referrer + relativedelta(months=1, day=1)
    begin = date_referrer.replace(day=1)

    params = {
        'begin': begin,
        'end': end,
    }

    count_payment = """
        SELECT
            COALESCE(SUM(value), 0) as amount_payment_total
        FROM
            financial_payment fp
        WHERE 1=1
            AND fp.user_id=%(user_id)s
            AND fp.type=1
            AND fp.status=0
            AND fp.active=true
            AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
    """

    with connection.cursor() as cursor:
        cursor.execute(count_payment, {**params, 'user_id': user.id})
        amount_payment_total = cursor.fetchone()

    return JsonResponse({'data': amount_payment_total})


@add_cors_react_dev
@validate_super_user
@require_GET
def report_amount_payment_closed_view(request, user):
    date_referrer = datetime.now().date()

    end = date_referrer + relativedelta(months=1, day=1)
    begin = date_referrer.replace(day=1)

    params = {
        'begin': begin,
        'end': end,
    }

    count_payment = """
        SELECT
            COALESCE(SUM(value), 0) as amount_payment_total
        FROM
            financial_payment fp
        WHERE 1=1
            AND fp.user_id=%(user_id)s
            AND fp.type=1
            AND fp.status=1
            AND fp.active=true
            AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
    """

    with connection.cursor() as cursor:
        cursor.execute(count_payment, {**params, 'user_id': user.id})
        amount_payment_total = cursor.fetchone()

    return JsonResponse({'data': amount_payment_total})


@add_cors_react_dev
@validate_super_user
@require_GET
def report_amount_invoice_by_tag_view(request, user):
    amount_invoice = """
        SELECT
            ft.id,
            ft."name",
            COALESCE(ft.color, '#000'),
            sum(fi.value)
        FROM
            financial_tag ft
        INNER JOIN financial_invoice_tags fit ON
            ft.id = fit.tag_id
        INNER JOIN financial_invoice fi ON
            fit.invoice_id = fi.id
        WHERE
            ft.user_id=%(user_id)s
        GROUP BY
            ft.id
        ORDER BY
            sum(fi.value) DESC;
    """
    with connection.cursor() as cursor:
        cursor.execute(amount_invoice, {'user_id': user.id})
        amount_invoice = cursor.fetchall()

    tags = [{
        'id': data[0],
        'name': data[1],
        'color': data[2],
        'amount': float(data[3])
    } for data in amount_invoice]

    return JsonResponse({'data': tags})
