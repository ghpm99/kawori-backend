class MetricsOverviewUseCase:
    def execute(
        self,
        queryset,
        period,
        q_fn,
        count_cls,
        sum_cls,
        avg_cls,
        to_float_fn,
        ratio_fn,
    ):
        summary = queryset.aggregate(
            total_calls=count_cls("id"),
            total_cost=sum_cls("cost_estimate"),
            success_calls=count_cls("id", filter=q_fn(success=True)),
            failed_calls=count_cls("id", filter=q_fn(success=False)),
            fallback_calls=count_cls("id", filter=q_fn(used_fallback=True)),
            retry_attempts=sum_cls("retry_count"),
            cache_hits=count_cls("id", filter=q_fn(cache_status="hit")),
            cache_misses=count_cls("id", filter=q_fn(cache_status="miss")),
            cache_bypass=count_cls("id", filter=q_fn(cache_status="bypass")),
            avg_latency_ms=avg_cls("latency_ms"),
            prompt_tokens=sum_cls("prompt_tokens"),
            completion_tokens=sum_cls("completion_tokens"),
            total_tokens=sum_cls("total_tokens"),
        )

        total_calls = int(summary.get("total_calls") or 0)
        success_calls = int(summary.get("success_calls") or 0)
        fallback_calls = int(summary.get("fallback_calls") or 0)
        retry_attempts = int(summary.get("retry_attempts") or 0)
        cache_hits = int(summary.get("cache_hits") or 0)

        response = {
            "period": period,
            "totals": {
                "calls": total_calls,
                "success_calls": success_calls,
                "failed_calls": int(summary.get("failed_calls") or 0),
                "cost_usd": to_float_fn(summary.get("total_cost")),
                "fallback_calls": fallback_calls,
                "retry_attempts": retry_attempts,
                "cache_hits": cache_hits,
                "cache_misses": int(summary.get("cache_misses") or 0),
                "cache_bypass": int(summary.get("cache_bypass") or 0),
                "avg_latency_ms": to_float_fn(summary.get("avg_latency_ms")),
                "prompt_tokens": int(summary.get("prompt_tokens") or 0),
                "completion_tokens": int(summary.get("completion_tokens") or 0),
                "total_tokens": int(summary.get("total_tokens") or 0),
            },
            "rates": {
                "success_rate": ratio_fn(success_calls, total_calls),
                "fallback_rate": ratio_fn(fallback_calls, total_calls),
                "retry_rate": ratio_fn(retry_attempts, total_calls),
                "cache_hit_rate": ratio_fn(cache_hits, total_calls),
            },
            "cardinality": {
                "features": queryset.values("feature_name")
                .exclude(feature_name="")
                .distinct()
                .count(),
                "providers": queryset.values("provider")
                .exclude(provider="")
                .distinct()
                .count(),
                "models": queryset.values("model").exclude(model="").distinct().count(),
                "task_types": queryset.values("task_type")
                .exclude(task_type="")
                .distinct()
                .count(),
            },
        }
        return {"data": response}, 200
