from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

handler404 = 'apps.inspecoes.views.erro_404'
handler403 = 'apps.inspecoes.views.erro_403'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('django.contrib.auth.urls')),
    path('', include('apps.inspecoes.urls', namespace='inspecoes')),
    path('', include('apps.edificacoes.urls', namespace='edificacoes')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
