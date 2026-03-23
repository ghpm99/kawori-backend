class EmailPreferencesUseCase:
    def build_payload(self, preference):
        return {
            "allow_all_emails": preference.allow_all_emails,
            "allow_notification": preference.allow_notification,
            "allow_promotional": preference.allow_promotional,
        }

    def execute_get(self, user, user_email_preference_model):
        pref, _ = user_email_preference_model.objects.get_or_create(user=user)
        return self.build_payload(pref), 200

    def execute_put(self, user, data, user_email_preference_model, allowed_fields):
        pref, _ = user_email_preference_model.objects.get_or_create(user=user)

        changed_fields = []
        for field in allowed_fields:
            if field in data:
                setattr(pref, field, data[field])
                changed_fields.append(field)

        if changed_fields:
            pref.save(update_fields=changed_fields + ["updated_at"])

        return self.build_payload(pref), 200
