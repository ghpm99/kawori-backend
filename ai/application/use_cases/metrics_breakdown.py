class MetricsBreakdownUseCase:
    def execute(
        self,
        queryset,
        period,
        group_by,
        q_fn,
        count_cls,
        sum_cls,
        avg_cls,
        to_float_fn,
        ratio_fn,
    ):
        group_by = str(group_by or "feature_name").strip()
        allowed_groups = {
            "feature_name",
            "provider",
            "model",
            "task_type",
            "cache_status",
            "success",
        }
        if group_by not in allowed_groups:
            return {"msg": "group_by inválido"}, 400

        rows = (
            queryset.values(group_by)
            .annotate(
                calls=count_cls("id"),
                success_calls=count_cls("id", filter=q_fn(success=True)),
                failed_calls=count_cls("id", filter=q_fn(success=False)),
                fallback_calls=count_cls("id", filter=q_fn(used_fallback=True)),
                retry_attempts=sum_cls("retry_count"),
                cost_usd=sum_cls("cost_estimate"),
                avg_latency_ms=avg_cls("latency_ms"),
                prompt_tokens=sum_cls("prompt_tokens"),
                completion_tokens=sum_cls("completion_tokens"),
                total_tokens=sum_cls("total_tokens"),
            )
            .order_by("-calls", group_by)
        )

        data = []
        for row in rows:
            calls = int(row.get("calls") or 0)
            success_calls = int(row.get("success_calls") or 0)
            data.append(
                {
                    "group": row.get(group_by),
                    "calls": calls,
                    "success_calls": success_calls,
                    "failed_calls": int(row.get("failed_calls") or 0),
                    "success_rate": ratio_fn(success_calls, calls),
                    "fallback_calls": int(row.get("fallback_calls") or 0),
                    "retry_attempts": int(row.get("retry_attempts") or 0),
                    "cost_usd": to_float_fn(row.get("cost_usd")),
                    "avg_latency_ms": to_float_fn(row.get("avg_latency_ms")),
                    "prompt_tokens": int(row.get("prompt_tokens") or 0),
                    "completion_tokens": int(row.get("completion_tokens") or 0),
                    "total_tokens": int(row.get("total_tokens") or 0),
                }
            )

        return {"data": {"group_by": group_by, "period": period, "rows": data}}, 200
