class MetricsEventsUseCase:
    def execute(
        self,
        queryset,
        period,
        page,
        page_size,
        to_positive_int_fn,
        to_float_fn,
    ):
        page = to_positive_int_fn(page, default=1)
        page_size = to_positive_int_fn(page_size, default=50)
        page_size = min(page_size, 200)

        total = queryset.count()
        offset = (page - 1) * page_size
        events = queryset.order_by("-created_at")[offset : offset + page_size]

        data = [
            {
                "id": event.id,
                "created_at": (
                    event.created_at.isoformat() if event.created_at else None
                ),
                "trace_id": event.trace_id,
                "feature_name": event.feature_name,
                "task_type": event.task_type,
                "provider": event.provider,
                "model": event.model,
                "success": event.success,
                "attempts": event.attempts,
                "retry_count": event.retry_count,
                "used_fallback": event.used_fallback,
                "latency_ms": event.latency_ms,
                "cache_status": event.cache_status,
                "prompt_tokens": event.prompt_tokens,
                "completion_tokens": event.completion_tokens,
                "total_tokens": event.total_tokens,
                "cost_estimate": to_float_fn(event.cost_estimate),
                "error_message": event.error_message,
                "metadata": event.metadata,
                "user_id": event.user_id,
            }
            for event in events
        ]

        return {
            "data": {
                "period": period,
                "page": page,
                "page_size": page_size,
                "total": total,
                "rows": data,
            }
        }, 200
