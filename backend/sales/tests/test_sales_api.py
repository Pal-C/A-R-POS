
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Product
from customers.models import Customer
from inventory.models import InventoryMovement
from sales.models import Payment, Sale

User = get_user_model()


class SalesAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            password="test-password",
        )
        self.client.force_authenticate(user=self.user)

        self.product = Product.objects.create(
            sku="RKT-001",
            name="Test Badminton Racket",
            category=Product.Category.RACKET,
            selling_price=Decimal("1500.00"),
            cost_price=Decimal("1000.00"),
            stock_quantity=10,
            low_stock_threshold=2,
            is_active=True,
        )

        self.customer = Customer.objects.create(
            full_name="Test Customer",
            phone_number="09123456789",
        )

        self.sales_url = reverse("sale-list-create")
        self.payments_url = reverse("payment-list-create")

    def sale_payload(self, **overrides):
        payload = {
            "customer_id": self.customer.pk,
            "discount_amount": "100.00",
            "items": [
                {
                    "product_id": self.product.pk,
                    "quantity": 2,
                    "discount_amount": "50.00",
                }
            ],
        }
        payload.update(overrides)
        return payload

    def create_and_finalize_sale(self):
        response = self.client.post(
            self.sales_url,
            self.sale_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        sale_id = response.data["id"]

        response = self.client.post(
            reverse("sale-finalize", kwargs={"pk": sale_id}),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        return Sale.objects.get(pk=sale_id)

    # ------------------------------
    # Sale creation
    # ------------------------------

    def test_create_draft_sale(self):
        response = self.client.post(
            self.sales_url,
            self.sale_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        sale = Sale.objects.get(pk=response.data["id"])

        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertEqual(sale.subtotal, Decimal("3000.00"))
        self.assertEqual(sale.discount_amount, Decimal("100.00"))
        self.assertEqual(sale.total_amount, Decimal("2850.00"))

        item = sale.items.get()

        self.assertEqual(item.unit_selling_price, Decimal("1500.00"))
        self.assertEqual(item.unit_cost_price, Decimal("1000.00"))

        # Draft creation must not deduct stock.
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

        self.assertFalse(
            InventoryMovement.objects.filter(
                sale_item__sale=sale
            ).exists()
        )

    def test_create_sale_without_items_is_rejected(self):
        response = self.client.post(
            self.sales_url,
            {
                "items": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_create_sale_with_duplicate_products_is_rejected(self):
        payload = self.sale_payload()
        payload["items"].append({
            "product_id": self.product.pk,
            "quantity": 1,
        })

        response = self.client.post(
            self.sales_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)

    def test_create_sale_with_inactive_product_is_rejected(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        response = self.client.post(
            self.sales_url,
            self.sale_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_create_sale_with_excessive_item_discount_is_rejected(self):
        payload = self.sale_payload()
        payload["items"][0]["discount_amount"] = "4000.00"

        response = self.client.post(
            self.sales_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)

    def test_create_sale_with_excessive_sale_discount_is_rejected(self):
        payload = self.sale_payload(discount_amount="4000.00")

        response = self.client.post(
            self.sales_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)

    # ------------------------------
    # Sale retrieval
    # ------------------------------

    def test_list_sales(self):
        self.client.post(
            self.sales_url,
            self.sale_payload(),
            format="json",
        )

        response = self.client.get(self.sales_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_retrieve_sale_details(self):
        sale_response = self.client.post(
            self.sales_url,
            self.sale_payload(),
            format="json",
        )
        sale_id = sale_response.data["id"]

        response = self.client.get(
            reverse("sale-detail", kwargs={"pk": sale_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(
            response.data["customer_name"],
            self.customer.full_name,
        )

    # ------------------------------
    # Finalization
    # ------------------------------

    def test_finalize_sale_deducts_inventory(self):
        sale_response = self.client.post(
            self.sales_url,
            self.sale_payload(),
            format="json",
        )
        sale_id = sale_response.data["id"]

        response = self.client.post(
            reverse("sale-finalize", kwargs={"pk": sale_id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        sale = Sale.objects.get(pk=sale_id)
        self.product.refresh_from_db()

        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertEqual(self.product.stock_quantity, 8)

        movement = InventoryMovement.objects.get(
            sale_item__sale=sale,
            movement_type=InventoryMovement.MovementType.SALE,
        )
        self.assertEqual(movement.quantity_change, -2)

    def test_finalize_sale_twice_is_rejected(self):
        sale_response = self.client.post(
            self.sales_url,
            self.sale_payload(),
            format="json",
        )
        sale_id = sale_response.data["id"]

        url = reverse("sale-finalize", kwargs={"pk": sale_id})

        first_response = self.client.post(url, {}, format="json")
        second_response = self.client.post(url, {}, format="json")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)

    # ------------------------------
    # Payments
    # ------------------------------

    def test_record_partial_payment(self):
        sale = self.create_and_finalize_sale()

        response = self.client.post(
            self.payments_url,
            {
                "sale": sale.pk,
                "amount": "1000.00",
                "payment_method": Payment.Method.CASH,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertEqual(sale.amount_paid, Decimal("1000.00"))
        self.assertEqual(sale.balance, Decimal("1850.00"))

    def test_full_payment_completes_sale(self):
        sale = self.create_and_finalize_sale()

        response = self.client.post(
            self.payments_url,
            {
                "sale": sale.pk,
                "amount": "2850.00",
                "payment_method": Payment.Method.GCASH,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.COMPLETED)

    def test_payment_exceeding_balance_is_rejected(self):
        sale = self.create_and_finalize_sale()

        response = self.client.post(
            self.payments_url,
            {
                "sale": sale.pk,
                "amount": "3000.00",
                "payment_method": Payment.Method.CASH,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Payment.objects.filter(sale=sale).count(), 0)

    def test_payment_requires_exactly_one_target(self):
        response = self.client.post(
            self.payments_url,
            {
                "amount": "100.00",
                "payment_method": Payment.Method.CASH,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_refund_reopens_sale_balance(self):
        sale = self.create_and_finalize_sale()

        self.client.post(
            self.payments_url,
            {
                "sale": sale.pk,
                "amount": "2850.00",
                "payment_method": Payment.Method.CASH,
            },
            format="json",
        )

        response = self.client.post(
            self.payments_url,
            {
                "sale": sale.pk,
                "amount": "500.00",
                "payment_method": Payment.Method.CASH,
                "payment_type": Payment.PaymentType.REFUND,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertEqual(sale.amount_paid, Decimal("2350.00"))

    # ------------------------------
    # Cancellation
    # ------------------------------

    def test_cancel_sale_reverses_inventory(self):
        sale = self.create_and_finalize_sale()

        response = self.client.post(
            reverse("sale-cancel", kwargs={"pk": sale.pk}),
            {"reason": "Customer changed their mind."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        sale.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(sale.status, Sale.Status.CANCELLED)
        self.assertEqual(self.product.stock_quantity, 10)

        self.assertEqual(
            InventoryMovement.objects.filter(
                sale_item__sale=sale,
                movement_type=InventoryMovement.MovementType.SALE,
            ).count(),
            1,
        )

        self.assertEqual(
            InventoryMovement.objects.filter(
                reversal_of__sale_item__sale=sale
            ).count(),
            1,
        )

    def test_cancel_sale_requires_reason(self):
        sale = self.create_and_finalize_sale()

        response = self.client.post(
            reverse("sale-cancel", kwargs={"pk": sale.pk}),
            {"reason": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_cancel_sale_twice_is_rejected(self):
        sale = self.create_and_finalize_sale()
        url = reverse("sale-cancel", kwargs={"pk": sale.pk})

        first_response = self.client.post(
            url,
            {"reason": "Cancellation test"},
            format="json",
        )
        second_response = self.client.post(
            url,
            {"reason": "Duplicate cancellation"},
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)
