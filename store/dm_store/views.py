from decimal import Decimal, InvalidOperation
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAdminUser
from django.db import transaction
from django.db.models import Sum, Count, F
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required

from .models import (
    StoreSettings, Category, Product,
    Customer, Cart, CartItem, Order, OrderItem
)
from .serializers import (
    StoreSettingsSerializer, CategorySerializer, ProductSerializer,
    CartSerializer, OrderSerializer, POSSyncItemSerializer
)


class StoreSettingsView(APIView):
    """عرض وتحديث إعدادات المتجر"""
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        settings_obj = StoreSettings.load()
        return Response(StoreSettingsSerializer(settings_obj).data)

    def patch(self, request):
        settings_obj = StoreSettings.load()
        serializer = StoreSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    """إدارة وعرض الأقسام"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAdminUser()]


class ProductViewSet(viewsets.ModelViewSet):
    """إدارة وعرض المنتجات والمخزن"""
    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "sku", "description"]
    ordering_fields = ["selling_price", "created_at", "stock_quantity"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        category_id = self.request.query_params.get("category")
        if category_id:
            qs = qs.filter(category_id=category_id)
        if not self.request.user.is_staff:
            qs = qs.filter(is_active=True)
        return qs


class CartAPIView(APIView):
    """إدارة سلة المشتريات للزبون (عرض، إضافة، تعديل، حذف)"""
    permission_classes = [AllowAny]

    def _get_customer_cart(self, phone, name="زبون"):
        customer, _ = Customer.objects.get_or_create(
            phone=phone.strip(),
            defaults={"name": name.strip() or "زبون"}
        )
        cart, _ = Cart.objects.get_or_create(customer=customer)
        return cart

    def get(self, request):
        phone = request.query_params.get("phone", "").strip()
        if not phone:
            return Response({"detail": "يرجى تمرير رقم الهاتف."}, status=status.HTTP_400_BAD_REQUEST)

        cart = self._get_customer_cart(phone)
        return Response(CartSerializer(cart).data)

    def post(self, request):
        """إضافة منتج إلى السلة أو تحديث كميته"""
        phone = request.data.get("phone", "").strip()
        name = request.data.get("name", "زبون").strip()
        product_id = request.data.get("product_id")
        quantity = int(request.data.get("quantity", 1))

        if not phone or not product_id:
            return Response(
                {"detail": "رقم الهاتف ورقم المنتج مطلوبان."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({"detail": "المنتج غير موجود."}, status=status.HTTP_404_NOT_FOUND)

        if quantity > product.stock_quantity:
            return Response(
                {"detail": f"الكمية المتوفرة في المخزن هي {product.stock_quantity} فقط."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = self._get_customer_cart(phone, name)

        if quantity <= 0:
            CartItem.objects.filter(cart=cart, product=product).delete()
        else:
            item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={"quantity": quantity}
            )
            if not created:
                item.quantity = quantity
                item.save(update_fields=["quantity"])

        return Response(CartSerializer(cart).data)

    def delete(self, request):
        """حذف منتج معين من السلة"""
        phone = request.data.get("phone", "").strip()
        product_id = request.data.get("product_id")

        if not phone or not product_id:
            return Response({"detail": "بيانات ناقصة."}, status=status.HTTP_400_BAD_REQUEST)

        cart = self._get_customer_cart(phone)
        CartItem.objects.filter(cart=cart, product_id=product_id).delete()
        return Response(CartSerializer(cart).data)


class OrderViewSet(viewsets.ModelViewSet):
    """إدارة الطلبات، إتمام الشراء من السلة، وتتبع الطلبات"""
    queryset = Order.objects.prefetch_related("items__product").select_related("customer").all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.action in ["checkout", "track"]:
            return [AllowAny()]
        return [IsAdminUser()]

    @staticmethod
    def _parse_coordinate(value):
        """تحويل آمن لإحداثيات GPS إلى Decimal مع التقريب لـ 6 منازل عشرية"""
        if value in [None, ""]:
            return None
        try:
            return Decimal(str(value)).quantize(Decimal("0.000001"))
        except (InvalidOperation, ValueError):
            return None

    @action(detail=False, methods=["post"], url_path="checkout")
    @transaction.atomic
    def checkout(self, request):
        """تحويل سلة الزبون إلى طلب رسمي مع إحداثيات الخريطة وتفريغ السلة"""
        phone = request.data.get("phone", "").strip()
        name = request.data.get("name", "").strip()
        city = request.data.get("city", "").strip()
        address = request.data.get("address", "").strip()
        notes = request.data.get("notes", "").strip()
        delivery_fee = Decimal(str(request.data.get("delivery_fee", 0) or 0))
        latitude = self._parse_coordinate(request.data.get("latitude"))
        longitude = self._parse_coordinate(request.data.get("longitude"))

        if not all([phone, name, city, address]):
            return Response(
                {"detail": "يرجى تعبئة الاسم، رقم الهاتف، المدينة، والعنوان."},
                status=status.HTTP_400_BAD_REQUEST
            )

        customer, _ = Customer.objects.update_or_create(
            phone=phone,
            defaults={"name": name}
        )

        try:
            cart = customer.cart
        except Cart.DoesNotExist:
            return Response({"detail": "سلة المشتريات فارغة."}, status=status.HTTP_400_BAD_REQUEST)

        cart_items = cart.items.select_related("product").all()
        if not cart_items.exists():
            return Response({"detail": "سلة المشتريات فارغة."}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.create(
            customer=customer,
            city=city,
            address=address,
            latitude=latitude,
            longitude=longitude,
            notes=notes,
            delivery_fee=delivery_fee
        )

        subtotal = Decimal("0.00")
        total_profit = Decimal("0.00")

        for item in cart_items:
            product = item.product
            if product.stock_quantity < item.quantity:
                raise DjangoValidationError(f"الكمية المطلوبة من ({product.name}) لم تعد متوفرة.")

            unit_price = product.final_price
            unit_cost = product.cost_price

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item.quantity,
                unit_price=unit_price,
                unit_cost=unit_cost
            )
            subtotal += unit_price * item.quantity
            total_profit += (unit_price - unit_cost) * item.quantity

        order.subtotal = subtotal
        order.total_amount = subtotal + order.delivery_fee
        order.total_profit = total_profit
        order.save(update_fields=["subtotal", "total_amount", "total_profit"])

        # تفريغ السلة بعد نجاح إنشاء الطلب
        cart_items.delete()

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="track")
    def track(self, request):
        """تتبع الزبون لطلباته عبر رقم الهاتف"""
        phone = request.query_params.get("phone", "").strip()
        if not phone:
            return Response({"detail": "يرجى إدخال رقم الهاتف."}, status=status.HTTP_400_BAD_REQUEST)

        orders = Order.objects.filter(customer__phone=phone).prefetch_related("items__product")
        return Response(OrderSerializer(orders, many=True).data)

    @action(detail=True, methods=["post"], url_path="update-status")
    def update_status(self, request, pk=None):
        """تحديث حالة الطلب من لوحة التحكم مع خصم/إرجاع المخزون تلقائياً"""
        order = self.get_object()
        new_status = request.data.get("status")

        if new_status not in Order.Status.values:
            return Response({"detail": "حالة طلب غير صالحة."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order.change_status(new_status)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderSerializer(order).data)


class DashboardAnalyticsView(APIView):
    """صفحة الإحصائيات والتقارير للوحة تحكم الإدارة"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        valid_statuses = [Order.Status.CONFIRMED, Order.Status.SHIPPED, Order.Status.DELIVERED]
        valid_orders = Order.objects.filter(status__in=valid_statuses)

        stats = valid_orders.aggregate(
            total_revenue=Sum("subtotal"),
            total_profit=Sum("total_profit"),
            confirmed_orders=Count("id")
        )

        pending_orders = Order.objects.filter(status=Order.Status.PENDING).count()
        low_stock_products = Product.objects.filter(
            stock_quantity__lte=3,
            is_active=True
        ).values("id", "sku", "name", "stock_quantity")

        top_selling = (
            OrderItem.objects.filter(order__status__in=valid_statuses)
            .values("product__id", "product__name", "product__sku")
            .annotate(total_sold=Sum("quantity"), revenue=Sum(F("quantity") * F("unit_price")))
            .order_by("-total_sold")[:5]
        )

        return Response({
            "total_revenue": stats["total_revenue"] or 0,
            "total_profit": stats["total_profit"] or 0,
            "confirmed_orders_count": stats["confirmed_orders"] or 0,
            "pending_orders_count": pending_orders,
            "low_stock_products": list(low_stock_products),
            "top_selling_products": list(top_selling),
        })


class POSSyncAPIView(APIView):
    """نقطة مزامنة الأسعار والكميات مع منظومة المحل المحلية"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = POSSyncItemSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        updated_count = 0
        not_found_skus = []

        for item in serializer.validated_data:
            updated = Product.objects.filter(sku=item["sku"]).update(
                selling_price=item["selling_price"],
                stock_quantity=item["stock_quantity"]
            )
            if updated:
                updated_count += 1
            else:
                not_found_skus.append(item["sku"])

        return Response({
            "updated_products": updated_count,
            "not_found_skus": not_found_skus
        })



def home_page(request):
    return render(request, "dm_store/index.html", {
        "store_settings": StoreSettings.load(),
        "categories": Category.objects.all(),
    })

def cart_page(request):
    return render(request, "dm_store/cart.html", {
        "store_settings": StoreSettings.load(),
    })

def track_page(request):
    return render(request, "dm_store/track.html", {
        "store_settings": StoreSettings.load(),
    })

@staff_member_required(login_url="/admin/login/")
def dashboard_page(request):
    return render(request, "dm_store/dashboard.html", {
        "store_settings": StoreSettings.load(),
    })