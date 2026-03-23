class GetNewUsersUseCase:
    def execute(self, user_model, datetime_cls, timedelta_cls):
        date_joined = datetime_cls.now() - timedelta_cls(days=7)
        new_users_count = user_model.objects.filter(
            is_active=True, date_joined=date_joined
        ).count()
        return {"new_users": new_users_count}, 200
