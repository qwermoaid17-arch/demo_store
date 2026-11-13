from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"products", views.ProductViewSet, basename="product")

urlpatterns = [
    path("", include(router.urls)),
    path("quick-auth/", views.quick_auth_login, name="quick-auth"),
    path("cart/", views.cart_api, name="cart-api"),
    path("orders/checkout/", views.checkout_api, name="checkout-api"),
    path("orders/track/", views.track_orders_api, name="track-orders-api"),
    path("orders/", views.admin_orders_api, name="admin-orders-api"),
    path("orders/<int:order_id>/update-status/", views.update_order_status_api, name="update-order-status"),
    path("dashboard/analytics/", views.dashboard_analytics_api, name="dashboard-analytics"),
]