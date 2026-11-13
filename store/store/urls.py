from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dm_store.views import home_page
from dm_store.views import home_page, cart_page, track_page, dashboard_page

admin.site.site_url = "/dashboard/"
admin.site.site_header = "إدارة متجر بيت الجمال للعطور"
admin.site.site_title = "لوحة التحكم"

urlpatterns = [
    path("", home_page, name="home"),
    path("cart/", cart_page, name="cart"),
    path("track/", track_page, name="track"),
    path("dashboard/", dashboard_page, name="dashboard"),
    path("admin/", admin.site.urls),
    path("api/", include("dm_store.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)