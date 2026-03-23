class GetAuditLogsUseCase:
    def execute(
        self,
        request_get,
        audit_log_model,
        format_date_fn,
        paginate_fn,
        timedelta_cls,
    ):
        req = request_get
        filters = {}

        if req.get("action"):
            filters["action"] = req.get("action")
        if req.get("category"):
            filters["category"] = req.get("category")
        if req.get("result"):
            filters["result"] = req.get("result")
        if req.get("user_id"):
            filters["user_id"] = req.get("user_id")
        if req.get("username"):
            filters["username__icontains"] = req.get("username")
        if req.get("ip_address"):
            filters["ip_address"] = req.get("ip_address")
        if req.get("date_from"):
            date_from = format_date_fn(req.get("date_from"))
            if date_from:
                filters["created_at__gte"] = date_from
        if req.get("date_to"):
            date_to = format_date_fn(req.get("date_to"))
            if date_to:
                filters["created_at__lte"] = date_to + timedelta_cls(days=1)

        logs = audit_log_model.objects.filter(**filters)
        page_size = req.get("page_size", 50)
        data = paginate_fn(logs, req.get("page", 1), page_size)

        logs_data = [
            {
                "id": log.id,
                "action": log.action,
                "category": log.category,
                "result": log.result,
                "user_id": log.user_id,
                "username": log.username,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "path": log.path,
                "method": log.method,
                "target_model": log.target_model,
                "target_id": log.target_id,
                "detail": log.detail,
                "response_status": log.response_status,
                "created_at": log.created_at.isoformat(),
            }
            for log in data.get("data")
        ]

        data["page_size"] = page_size
        data["data"] = logs_data
        return {"data": data}, 200
