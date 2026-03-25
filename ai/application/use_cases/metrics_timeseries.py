class MetricsTimeseriesUseCase:
    def execute(
        self,
        queryset,
        period,
        interval,
        trunc_hour_fn,
        trunc_date_fn,
        count_cls,
        q_fn,
        sum_cls,
        avg_cls,
        ratio_fn,
        to_float_fn,
    ):
        interval = str(interval or "day").strip().lower()
        if interval not in {"day", "hour"}:
            return {"msg": "interval inválido"}, 400

        bucket_fn = (
            trunc_hour_fn("created_at")
            if interval == "hour"
            else trunc_date_fn("created_at")
        )
        rows = (
            queryset.annotate(bucket=bucket_fn)
            .values("bucket")
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
                cache_hits=count_cls("id", filter=q_fn(cache_status="hit")),
            )
            .order_by("bucket")
        )

        data = []
        for row in rows:
            calls = int(row.get("calls") or 0)
            success_calls = int(row.get("success_calls") or 0)
            bucket = row.get("bucket")
            data.append(
                {
                    "bucket": bucket.isoformat() if bucket else None,
                    "calls": calls,
                    "success_calls": success_calls,
                    "failed_calls": int(row.get("failed_calls") or 0),
                    "success_rate": ratio_fn(success_calls, calls),
                    "fallback_calls": int(row.get("fallback_calls") or 0),
                    "retry_attempts": int(row.get("retry_attempts") or 0),
                    "cache_hits": int(row.get("cache_hits") or 0),
                    "cost_usd": to_float_fn(row.get("cost_usd")),
                    "avg_latency_ms": to_float_fn(row.get("avg_latency_ms")),
                    "prompt_tokens": int(row.get("prompt_tokens") or 0),
                    "completion_tokens": int(row.get("completion_tokens") or 0),
                    "total_tokens": int(row.get("total_tokens") or 0),
                }
            )

        return {"data": {"interval": interval, "period": period, "rows": data}}, 200
