import uuid
from decimal import Decimal
from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class StoreSettings(models.Model):
    store_name = models.CharField(max_length=150, default="TechSetup Store", verbose_name="اسم المتجر")
    tagline = models.CharField(max_length=255, blank=True, verbose_name="الوصف المختصر")
    logo = models.ImageField(upload_to="branding/", blank=True, null=True, verbose_name="شعار المتجر")
    phone_number = models.CharField(max_length=30, blank=True, verbose_name="رقم الهاتف")
    whatsapp_number = models.CharField(max_length=30, blank=True, verbose_name="رقم الواتساب")
    address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")

    class Meta:
        verbose_name = "إعدادات المتجر"
        verbose_name_plural = "إعدادات المتجر"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.store_name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم القسم")

    class Meta:
        verbose_name = "قسم"
        verbose_name_plural = "الأقسام"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="القسم"
    )
    sku = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="كود الصنف (SKU)",
        help_text="يستخدم للربط مع منظومة المحل المحلية"
    )
    name = models.CharField(max_length=200, verbose_name="اسم المنتج")
    description = models.TextField(blank=True, verbose_name="الوصف والمواصفات")
    image = models.ImageField(upload_to="products/", blank=True, null=True, verbose_name="صورة المنتج")

    # الأسعار والتخفيض والمخزن
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر التكلفة")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر البيع")
    discount_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="نسبة التخفيض (%)"
    )
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="الكمية المتوفرة")

    is_active = models.BooleanField(default=True, verbose_name="متاح للعرض")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "منتج"
        verbose_name_plural = "المنتجات والمخزن"
        ordering = ["-created_at"]

    @property
    def final_price(self):
        """حساب السعر النهائي بعد تطبيق نسبة التخفيض بدقة مالية"""
        if self.discount_percentage > 0:
            discount_amount = (self.selling_price * Decimal(self.discount_percentage)) / Decimal("100")
            return (self.selling_price - discount_amount).quantize(Decimal("0.01"))
        return self.selling_price

    @property
    def profit_per_unit(self):
        return self.final_price - self.cost_price

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Customer(models.Model):
    """حساب الزبون: جاهز لإضافة التحقق بالرمز (OTP) لاحقاً"""
    name = models.CharField(max_length=150, verbose_name="الاسم")
    phone = models.CharField(max_length=20, unique=True, verbose_name="رقم الهاتف")
    is_verified = models.BooleanField(default=False, verbose_name="تم التحقق من الرقم")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "زبون"
        verbose_name_plural = "الزبائن"

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Cart(models.Model):
    """سلة مشتريات مرتبطة بحساب الزبون"""
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="cart",
        verbose_name="الزبون"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "سلة مشتريات"
        verbose_name_plural = "سلات المشتريات"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())

    def __str__(self):
        return f"سلة: {self.customer.name}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", verbose_name="السلة")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="المنتج")
    quantity = models.PositiveIntegerField(default=1, verbose_name="الكمية")

    class Meta:
        verbose_name = "عنصر سلة"
        verbose_name_plural = "عناصر السلة"
        unique_together = ("cart", "product")

    @property
    def line_total(self):
        return self.product.final_price * self.quantity

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "قيد المراجعة"
        CONFIRMED = "confirmed", "مؤكد"
        SHIPPED = "shipped", "قيد التوصيل"
        DELIVERED = "delivered", "تم التسليم"
        CANCELLED = "cancelled", "ملغي"

    order_number = models.CharField(max_length=20, unique=True, editable=False, verbose_name="رقم الطلب")
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="الزبون"
    )
    # ... الحقول السابقة (order_number, customer, city, address...)
    city = models.CharField(max_length=100, verbose_name="المدينة")
    address = models.TextField(verbose_name="وصف العنوان (أقرب نقطة دالة)")
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="خط العرض (Latitude)"
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="خط الطول (Longitude)"
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات إضافية")
    # ... باقي الحقول كما هي

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="حالة الطلب"
    )
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="سعر التوصيل")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="مجموع المنتجات")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="الإجمالي الكلي")
    total_profit = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="صافي الربح")

    stock_deducted = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الطلب")

    @property
    def google_maps_url(self):
        if self.latitude and self.longitude:
            return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        return None

    class Meta:
        verbose_name = "طلب"
        verbose_name_plural = "الطلبات"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @transaction.atomic
    def change_status(self, new_status):
        """تغيير حالة الطلب مع خصم أو إرجاع الكميات من المخزن تلقائياً"""
        if new_status == self.status:
            return

        if new_status in [self.Status.CONFIRMED, self.Status.SHIPPED, self.Status.DELIVERED] and not self.stock_deducted:
            for item in self.items.select_related("product").all():
                product = Product.objects.select_for_update().get(id=item.product.id)
                if product.stock_quantity < item.quantity:
                    raise ValidationError(f"الكمية غير كافية في المخزن للمنتج: {product.name}")
                product.stock_quantity -= item.quantity
                product.save(update_fields=["stock_quantity"])
            self.stock_deducted = True

        elif new_status == self.Status.CANCELLED and self.stock_deducted:
            for item in self.items.select_related("product").all():
                product = Product.objects.select_for_update().get(id=item.product.id)
                product.stock_quantity += item.quantity
                product.save(update_fields=["stock_quantity"])
            self.stock_deducted = False

        self.status = new_status
        self.save(update_fields=["status", "stock_deducted"])

    def __str__(self):
        return f"{self.order_number} - {self.customer.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="الطلب")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="المنتج")
    quantity = models.PositiveIntegerField(default=1, verbose_name="الكمية")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر البيع وقت الطلب")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر التكلفة وقت الطلب")

    class Meta:
        verbose_name = "عنصر طلب"
        verbose_name_plural = "عناصر الطلبات"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"
    