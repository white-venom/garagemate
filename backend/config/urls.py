from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path("", core_views.api_index),
    path("admin/", admin.site.urls),
    path("api/", core_views.api_index, name="api-index"),
    path("api/health/", core_views.health, name="health"),
    path("api/", include("chat.urls")),
    path("api/", include("diagnosis.urls")),
    path("api/", include("bookings.urls")),
    path("api/", include("apilogs.urls")),
    path("api/", include("customers.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
