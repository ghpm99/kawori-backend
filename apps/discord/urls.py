from django.urls import path, include
from discord.views import user, guild

urlpatterns = [
    path('user/', include([
        path('', user.get_all_users, name='user_user_get_all'),
    ])),
    path('guild/', include([
        path('', guild.get_all_guilds, name='user_guild_get_all'),
        path('member/', include([
            path('', guild.get_all_members, name='guild_member_get_all'),
        ])),
        path('role/', include([
            path('', guild.get_all_roles, name='guild_role_get_all'),
        ]))
    ])),
]
