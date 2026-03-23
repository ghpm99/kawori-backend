class GetAuditStatsUseCase:
    def execute(self, audit_log_model, now_fn, timedelta_cls, count_cls):
        now = now_fn()
        last_24h = now - timedelta_cls(hours=24)
        last_7d = now - timedelta_cls(days=7)

        by_category_24h = (
            audit_log_model.objects.filter(created_at__gte=last_24h)
            .values("category")
            .annotate(count=count_cls("id"))
        )

        by_result_24h = (
            audit_log_model.objects.filter(created_at__gte=last_24h)
            .values("result")
            .annotate(count=count_cls("id"))
        )

        by_category_7d = (
            audit_log_model.objects.filter(created_at__gte=last_7d)
            .values("category")
            .annotate(count=count_cls("id"))
        )

        by_result_7d = (
            audit_log_model.objects.filter(created_at__gte=last_7d)
            .values("result")
            .annotate(count=count_cls("id"))
        )

        failed_logins_24h = audit_log_model.objects.filter(
            created_at__gte=last_24h,
            action="login",
            result="failure",
        ).count()

        return {
            "data": {
                "last_24h": {
                    "by_category": list(by_category_24h),
                    "by_result": list(by_result_24h),
                },
                "last_7d": {
                    "by_category": list(by_category_7d),
                    "by_result": list(by_result_7d),
                },
                "failed_logins_24h": failed_logins_24h,
            }
        }, 200
