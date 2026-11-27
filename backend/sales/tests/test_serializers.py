from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from sales.models import Payment, Sale
from sales.serializers import (
    PaymentCreateSerializer,
    PaymentSerializer,
    SaleCreateSerializer,
    SaleDetailSerializer,
    SaleItemAddSerializer,
    SaleItemUpdateSerializer,
    SaleListSerializer,
    SaleUpdateSerializer,
)
from sales.services import create_draft_sale, finalize_sale, record_payment
from sales.tests.factories import line, make_customer, make_product, make_user

D = Decimal


class SerializerTestCase(TestCase):
    def setUp(self):
        self.user = make_user()
        self.customer = make_customer()
        self.racket = make_product(name="Racket")  # 1500
        self.grip = make_product(name="Grip", selling_price=D("250.00"))
        request = APIRequestFactory().post("/")
        request.user = self.user
        self.context = {"request": request}

    def payload(self, **overrides):
        data = {
            "customer_id": self.customer.pk,
            "discount_amount": "100.00",
            "items": [
                {
                    "product_id": self.racket.pk,
                    "quantity": 2,
                    "discount_amount": "50.00",
                }
            ],
        }
        data.update(overrides)
        return data

    def create_serializer(self, data):
        return SaleCreateSerializer(data=data, context=self.context)

    def draft(self):
        return create_draft_sale(user=self.user, items=[line(self.racket, 2)])


class SaleCreateSerializerTests(SerializerTestCase):
    def test_valid_payload_creates_draft_sale(self):
        serializer = self.create_serializer(self.payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)

        sale = serializer.save()

        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertEqual(sale.customer, self.customer)
        self.assertEqual(sale.created_by, self.user)
        self.assertEqual(sale.total_amount, D("2850.00"))

    def test_customer_is_optional_and_nullable(self):
        omitted = self.payload()
        del omitted["customer_id"]

        for name, data in {
            "omitted": omitted,
            "null": self.payload(customer_id=None),
        }.items():
            with self.subTest(name):
                serializer = self.create_serializer(data)
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertIsNone(serializer.validated_data.get("customer"))

    def test_item_discount_defaults_to_zero(self):
        serializer = self.create_serializer(
            self.payload(items=[{"product_id": self.racket.pk, "quantity": 1}])
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["items"][0]["discount_amount"], 0)

    def assert_invalid(self, data, field):
        serializer = self.create_serializer(data)
        self.assertFalse(serializer.is_valid())
        self.assertIn(field, serializer.errors)
        return serializer.errors[field]

    def test_unknown_product_is_rejected(self):
        errors = self.assert_invalid(
            self.payload(items=[{"product_id": 999999, "quantity": 1}]), "items"
        )
        self.assertIn("does not exist", str(errors))

    def test_inactive_product_is_rejected_with_clear_message(self):
        inactive = make_product(name="Old Racket", is_active=False)
        errors = self.assert_invalid(
            self.payload(items=[{"product_id": inactive.pk, "quantity": 1}]), "items"
        )
        self.assertIn("Old Racket is inactive", str(errors))

    def test_unknown_customer_is_rejected(self):
        self.assert_invalid(self.payload(customer_id=999999), "customer_id")

    def test_archived_customer_is_rejected(self):
        archived = make_customer(full_name="Gone", is_active=False)
        errors = self.assert_invalid(
            self.payload(customer_id=archived.pk), "customer_id"
        )
        self.assertIn("archived", str(errors))

    def test_missing_or_empty_items_are_rejected(self):
        self.assert_invalid(self.payload(items=[]), "items")
        data = self.payload()
        del data["items"]
        self.assert_invalid(data, "items")

    def test_duplicate_products_are_rejected(self):
        errors = self.assert_invalid(
            self.payload(
                items=[
                    {"product_id": self.racket.pk, "quantity": 1},
                    {"product_id": self.racket.pk, "quantity": 2},
                ]
            ),
            "items",
        )
        self.assertIn("only appear once", str(errors))

    def test_invalid_quantities_are_rejected(self):
        for quantity in (0, -1, "abc", 1.5, None):
            with self.subTest(quantity=quantity):
                self.assert_invalid(
                    self.payload(
                        items=[{"product_id": self.racket.pk, "quantity": quantity}]
                    ),
                    "items",
                )

    def test_invalid_item_discounts_are_rejected(self):
        for discount in ("-0.01", "abc", "1.001", "3000.01"):
            with self.subTest(discount=discount):
                self.assert_invalid(
                    self.payload(
                        items=[
                            {
                                "product_id": self.racket.pk,
                                "quantity": 2,
                                "discount_amount": discount,
                            }
                        ]
                    ),
                    "items",
                )

    def test_invalid_sale_discounts_are_rejected(self):
        # Remaining after item discount: 3000 - 50 = 2950
        for discount in ("-1.00", "abc", "2950.01"):
            with self.subTest(discount=discount):
                self.assert_invalid(
                    self.payload(discount_amount=discount), "discount_amount"
                )

    def test_client_cannot_set_financial_or_historical_fields(self):
        data = self.payload(
            subtotal="1.00",
            total_amount="1.00",
            status=Sale.Status.COMPLETED,
            sale_number="FAKE-1",
            created_by=make_user().pk,
            finalized_at="2020-01-01T00:00:00Z",
        )
        data["items"][0].update(unit_selling_price="1.00", unit_cost_price="0.00")

        serializer = self.create_serializer(data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        sale = serializer.save()

        self.assertEqual(sale.subtotal, D("3000.00"))
        self.assertEqual(sale.total_amount, D("2850.00"))
        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertIsNone(sale.sale_number)
        self.assertIsNone(sale.finalized_at)
        self.assertEqual(sale.created_by, self.user)
        item = sale.items.get()
        self.assertEqual(item.unit_selling_price, D("1500.00"))
        self.assertEqual(item.unit_cost_price, D("1000.00"))


class DraftEditSerializerTests(SerializerTestCase):
    def test_add_item_validates_merged_discount(self):
        sale = self.draft()  # racket x2 (3000)
        context = {**self.context, "sale": sale}

        ok = SaleItemAddSerializer(
            data={
                "product_id": self.racket.pk,
                "quantity": 1,
                "discount_amount": "4500",
            },
            context=context,
        )
        self.assertTrue(ok.is_valid(), ok.errors)

        too_much = SaleItemAddSerializer(
            data={
                "product_id": self.racket.pk,
                "quantity": 1,
                "discount_amount": "4500.01",
            },
            context=context,
        )
        self.assertFalse(too_much.is_valid())

    def test_add_item_rejects_inactive_product_and_bad_quantity(self):
        sale = self.draft()
        context = {**self.context, "sale": sale}
        inactive = make_product(is_active=False)
        for data in (
            {"product_id": inactive.pk, "quantity": 1},
            {"product_id": self.grip.pk, "quantity": 0},
        ):
            with self.subTest(data=data):
                self.assertFalse(
                    SaleItemAddSerializer(data=data, context=context).is_valid()
                )

    def test_item_update_requires_a_field_and_valid_values(self):
        item = self.draft().items.get()
        cases = [
            {},
            {"quantity": 0},
            {"discount_amount": "-1"},
            {"discount_amount": "3000.01"},
        ]
        for data in cases:
            with self.subTest(data=data):
                self.assertFalse(SaleItemUpdateSerializer(item, data=data).is_valid())

        valid = SaleItemUpdateSerializer(item, data={"quantity": 3})
        self.assertTrue(valid.is_valid(), valid.errors)

    def test_sale_update_accepts_only_customer_and_discount(self):
        sale = self.draft()
        serializer = SaleUpdateSerializer(
            sale,
            data={
                "discount_amount": "10.00",
                "total_amount": "1.00",
                "status": "COMPLETED",
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(set(serializer.validated_data), {"discount_amount"})


class SaleReadSerializerTests(SerializerTestCase):
    def test_detail_includes_items_payments_and_computed_amounts(self):
        sale = create_draft_sale(
            user=self.user,
            customer=self.customer,
            items=[line(self.racket, 2, "50.00"), line(self.grip, 1)],
            discount_amount=D("100.00"),
        )
        sale = finalize_sale(sale.pk, self.user)
        record_payment(
            user=self.user,
            sale=sale,
            amount=D("1000.00"),
            payment_method=Payment.Method.CASH,
        )

        request = APIRequestFactory().get("/")
        request.user = make_user()
        request.user.is_superuser = True  # may view cost
        data = SaleDetailSerializer(
            Sale.objects.get(pk=sale.pk), context={"request": request}
        ).data

        self.assertEqual(data["customer_name"], self.customer.full_name)
        self.assertEqual(data["created_by_name"], self.user.username)
        self.assertEqual(data["subtotal"], "3250.00")
        self.assertEqual(data["item_discount_total"], "50.00")
        self.assertEqual(data["discount_amount"], "100.00")
        self.assertEqual(data["total_amount"], "3100.00")
        self.assertEqual(data["amount_paid"], "1000.00")
        self.assertEqual(data["balance"], "2100.00")
        self.assertEqual(data["refund_due"], "0.00")
        self.assertEqual(data["status"], Sale.Status.PENDING_PAYMENT)
        self.assertTrue(data["sale_number"])

        self.assertEqual(len(data["items"]), 2)
        racket = next(i for i in data["items"] if i["product"] == self.racket.pk)
        self.assertEqual(racket["product_name"], "Racket")
        self.assertEqual(racket["product_sku"], self.racket.sku)
        self.assertEqual(racket["unit_selling_price"], "1500.00")
        self.assertEqual(racket["unit_cost_price"], "1000.00")
        self.assertEqual(racket["line_subtotal"], "3000.00")
        self.assertEqual(racket["line_total"], "2950.00")
        self.assertEqual(racket["gross_profit"], "950.00")

        # Without the cost permission (or without a request) cost is hidden.
        hidden = SaleDetailSerializer(Sale.objects.get(pk=sale.pk)).data["items"][0]
        self.assertNotIn("unit_cost_price", hidden)
        self.assertNotIn("gross_profit", hidden)

        self.assertEqual(len(data["payments"]), 1)
        self.assertEqual(data["payments"][0]["amount"], "1000.00")

    def test_walk_in_sale_has_null_customer_name(self):
        data = SaleListSerializer(self.draft()).data
        self.assertIsNone(data["customer"])
        self.assertIsNone(data["customer_name"])

    def test_read_serializers_are_fully_read_only(self):
        for serializer_class in (
            SaleListSerializer,
            SaleDetailSerializer,
            PaymentSerializer,
        ):
            with self.subTest(serializer_class.__name__):
                writable = [
                    name
                    for name, field in serializer_class().fields.items()
                    if not field.read_only
                ]
                self.assertEqual(writable, [])


class PaymentCreateSerializerTests(SerializerTestCase):
    def setUp(self):
        super().setUp()
        self.sale = finalize_sale(self.draft().pk, self.user)  # total 3000

    def payment(self, **overrides):
        data = {
            "sale": self.sale.pk,
            "amount": "500.00",
            "payment_method": Payment.Method.CASH,
        }
        data.update(overrides)
        return PaymentCreateSerializer(data=data, context=self.context)

    def test_valid_receipt_is_recorded(self):
        serializer = self.payment(reference_number="OR-1")
        self.assertTrue(serializer.is_valid(), serializer.errors)
        payment = serializer.save()

        self.assertEqual(payment.payment_type, Payment.PaymentType.RECEIPT)
        self.assertEqual(payment.received_by, self.user)
        self.assertEqual(payment.reference_number, "OR-1")

    def test_refund_requires_reason_and_stores_it(self):
        receipt = self.payment(amount="1000.00")
        self.assertTrue(receipt.is_valid(), receipt.errors)
        receipt.save()

        missing = self.payment(payment_type=Payment.PaymentType.REFUND, amount="100.00")
        self.assertFalse(missing.is_valid())
        self.assertIn("notes", missing.errors)

        serializer = self.payment(
            payment_type=Payment.PaymentType.REFUND,
            amount="100.00",
            notes="Damaged grip",
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        refund = serializer.save()
        self.assertEqual(refund.payment_type, Payment.PaymentType.REFUND)
        self.assertEqual(refund.notes, "Damaged grip")

    def test_invalid_payments_are_rejected(self):
        cases = {
            "zero amount": dict(amount="0.00"),
            "negative amount": dict(amount="-1.00"),
            "too many decimals": dict(amount="1.001"),
            "bad method": dict(payment_method="BITCOIN"),
            "bad type": dict(payment_type="GIFT"),
            "unknown sale": dict(sale=999999),
            "no target": dict(sale=None),
        }
        for name, overrides in cases.items():
            with self.subTest(name):
                self.assertFalse(self.payment(**overrides).is_valid())

    def test_client_cannot_set_status_or_receiver(self):
        other = make_user()
        serializer = self.payment(
            status=Payment.Status.VOIDED,
            received_by=other.pk,
            payment_date="2020-01-01T00:00:00Z",
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        payment = serializer.save()

        self.assertEqual(payment.status, Payment.Status.POSTED)
        self.assertEqual(payment.received_by, self.user)
        self.assertNotEqual(payment.payment_date.year, 2020)
