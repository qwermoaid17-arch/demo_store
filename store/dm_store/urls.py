from . import views
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StoreSettingsView, CategoryViewSet, ProductViewSet,
    CartAPIView, OrderViewSet, DashboardAnalyticsView, POSSyncAPIView
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("", include(router.urls)),
    path("settings/", StoreSettingsView.as_view(), name="store-settings"),
    path("cart/", CartAPIView.as_view(), name="cart-api"),
    path("dashboard/analytics/", DashboardAnalyticsView.as_view(), name="dashboard-analytics"),
    path("pos/sync/", POSSyncAPIView.as_view(), name="pos-sync"),
    path("quick-auth/", views.quick_auth_login, name="quick-auth"),
]