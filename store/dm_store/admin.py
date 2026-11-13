from django.contrib import admin
from .models import StoreSettings, Category, Product, Customer, Cart, CartItem, Order, OrderItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["customer", "total_items", "subtotal", "updated_at"]
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "customer", "city", "status", "total_amount", "created_at"]
    list_filter = ["status", "city"]
    inlines = [OrderItemInline]


admin.site.register(StoreSettings)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Customer)