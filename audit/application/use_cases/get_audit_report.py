class GetAuditReportUseCase:
    def execute(
        self,
        request_get,
        audit_log_model,
        format_date_fn,
        timedelta_cls,
        trunc_date_cls,
        count_cls,
        build_ai_insights_fn,
    ):
        req = request_get
        filters = {}
        response_filters = {}

        if req.get("category"):
            filters["category"] = req.get("category")
            response_filters["category"] = req.get("category")
        if req.get("action"):
            filters["action"] = req.get("action")
            response_filters["action"] = req.get("action")
        if req.get("result"):
            filters["result"] = req.get("result")
            response_filters["result"] = req.get("result")
        if req.get("user_id"):
            filters["user_id"] = req.get("user_id")
            response_filters["user_id"] = req.get("user_id")
        if req.get("username"):
            filters["username__icontains"] = req.get("username")
            response_filters["username"] = req.get("username")
        if req.get("date_from"):
            date_from = format_date_fn(req.get("date_from"))
            if date_from:
                filters["created_at__gte"] = date_from
                response_filters["date_from"] = req.get("date_from")
        if req.get("date_to"):
            date_to = format_date_fn(req.get("date_to"))
            if date_to:
                filters["created_at__lte"] = date_to + timedelta_cls(days=1)
                response_filters["date_to"] = req.get("date_to")

        limit = int(req.get("limit", 10))
        if limit < 1:
            limit = 10
        if limit > 100:
            limit = 100

        logs = audit_log_model.objects.filter(**filters)

        summary = {
            "total_events": logs.count(),
            "unique_users": logs.exclude(username="").values("username").distinct().count(),
            "success_events": logs.filter(result="success").count(),
            "failure_events": logs.filter(result="failure").count(),
            "error_events": logs.filter(result="error").count(),
        }

        interactions_by_day = list(
            logs.annotate(day=trunc_date_cls("created_at"))
            .values("day")
            .annotate(count=count_cls("id"))
            .order_by("day")
        )
        interactions_by_day = [
            {"day": item["day"].isoformat() if item["day"] else None, "count": item["count"]}
            for item in interactions_by_day
        ]

        by_action = list(
            logs.values("action")
            .annotate(count=count_cls("id"))
            .order_by("-count", "action")[:limit]
        )
        by_category = list(
            logs.values("category")
            .annotate(count=count_cls("id"))
            .order_by("-count", "category")[:limit]
        )
        by_user = list(
            logs.exclude(username="")
            .values("username", "user_id")
            .annotate(count=count_cls("id"))
            .order_by("-count", "username")[:limit]
        )
        failures_by_action = list(
            logs.filter(result__in=["failure", "error"])
            .values("action")
            .annotate(count=count_cls("id"))
            .order_by("-count", "action")[:limit]
        )

        response_data = {
            "filters": response_filters,
            "summary": summary,
            "interactions_by_day": interactions_by_day,
            "by_action": by_action,
            "by_category": by_category,
            "by_user": by_user,
            "failures_by_action": failures_by_action,
        }

        ai_insights = build_ai_insights_fn(
            filters=response_filters,
            summary=summary,
            interactions_by_day=interactions_by_day,
            by_action=by_action,
            by_category=by_category,
            by_user=by_user,
            failures_by_action=failures_by_action,
        )
        if ai_insights:
            response_data["ai_insights"] = ai_insights

        return {"data": response_data}, 200
