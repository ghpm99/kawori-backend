from django.urls import path, include
from discord.views import user

urlpatterns = [
    path('user/', include([
        path('member/', include([
            path('', user.get_all_members, name='user_member_get_all'),
        ])),
        path('user/', include([
            path('', user.get_all_users, name='user_user_get_all'),
        ]))
    ])),
]
