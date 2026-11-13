from rest_framework import serializers
from .models import (
    StoreSettings, Category, Product,
    Customer, Cart, CartItem, Order, OrderItem
)


class StoreSettingsSerializer(serializers.ModelSerializer):
    google_maps_url = serializers.CharField(read_only=True)

    class Meta:
        model = StoreSettings
        fields = [
            "id", "store_name", "tagline", "logo",
            "phone_number", "whatsapp_number", "address",
            "latitude", "longitude", "google_maps_url"
        ]


class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "products_count"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "category", "category_name", "sku", "name", "description",
            "image", "cost_price", "selling_price", "discount_percentage",
            "final_price", "stock_quantity", "is_active", "created_at"
        ]


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_image = serializers.ImageField(source="product.image", read_only=True)
    unit_price = serializers.DecimalField(source="product.final_price", max_digits=10, decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_name", "product_image", "unit_price", "quantity", "line_total"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "items", "total_items", "subtotal", "updated_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "product_sku", "quantity", "unit_price", "line_total"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    google_maps_url = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "customer_name", "customer_phone",
            "city", "address", "latitude", "longitude", "google_maps_url",
            "notes", "status", "status_display",
            "delivery_fee", "subtotal", "total_amount", "total_profit",
            "items", "created_at"
        ]
        read_only_fields = ["order_number", "subtotal", "total_amount", "total_profit", "status"]


class POSSyncItemSerializer(serializers.Serializer):
    """نموذج استقبال تحديثات الأسعار والكميات من منظومة المحل المحلية"""
    sku = serializers.CharField(max_length=64)
    selling_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = serializers.IntegerField(min_value=0)