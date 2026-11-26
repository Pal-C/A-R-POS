
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Product

User = get_user_model()


class ProductAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="testadmin",
            email="test@example.com",
            password="testpassword123",
        )

        self.client.force_authenticate(user=self.user)

        self.product = Product.objects.create(
            sku="YON-001",
            name="Yonex Badminton Racket",
            category=Product.Category.RACKET,
            subcategory="Badminton",
            brand="Yonex",
            selling_price="4500.00",
            cost_price="3200.00",
            stock_quantity=10,
            low_stock_threshold=3,
        )

        self.list_url = reverse("product-list")

    # CREATE

    def test_create_product(self):
        data = {
            "sku": "LI-NING-001",
            "name": "Li-Ning Badminton Racket",
            "category": "RACKET",
            "subcategory": "Badminton",
            "brand": "Li-Ning",
            "selling_price": "3500.00",
            "cost_price": "2500.00",
            "low_stock_threshold": 5,
        }

        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Product.objects.filter(sku="LI-NING-001").exists()
        )

        product = Product.objects.get(sku="LI-NING-001")
        self.assertEqual(product.stock_quantity, 0)

    def test_duplicate_sku_is_rejected(self):
        data = {
            "sku": "YON-001",
            "name": "Another Racket",
            "category": "RACKET",
            "selling_price": "3000.00",
            "cost_price": "2000.00",
        }

        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_price_is_rejected(self):
        data = {
            "sku": "TEST-NEG",
            "name": "Invalid Product",
            "category": "RACKET",
            "selling_price": "-100.00",
            "cost_price": "50.00",
        }

        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # READ

    def test_list_products(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_product(self):
        url = reverse(
            "product-detail",
            args=[self.product.id],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sku"], "YON-001")

    # UPDATE

    def test_update_product(self):
        url = reverse(
            "product-detail",
            args=[self.product.id],
        )

        response = self.client.patch(
            url,
            {"selling_price": "4800.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()
        self.assertEqual(self.product.selling_price, Decimal("4800.00"))

    def test_stock_quantity_cannot_be_updated_through_product_api(self):
        url = reverse(
            "product-detail",
            args=[self.product.id],
        )

        response = self.client.patch(
            url,
            {"stock_quantity": 100},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)

    # DEACTIVATE / REACTIVATE

    def test_deactivate_product(self):
        url = reverse(
            "product-deactivate",
            args=[self.product.id],
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_reactivate_product(self):
        self.product.is_active = False
        self.product.save()

        url = reverse(
            "product-reactivate",
            args=[self.product.id],
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)

    def test_permanent_delete_is_not_allowed(self):
        url = reverse(
            "product-detail",
            args=[self.product.id],
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        self.assertTrue(
            Product.objects.filter(pk=self.product.id).exists()
        )

    # FILTERING AND SEARCH

    def test_search_products(self):
        response = self.client.get(
            self.list_url,
            {"search": "Yonex"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_category(self):
        response = self.client.get(
            self.list_url,
            {"category": "RACKET"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_stock_status(self):
        response = self.client.get(
            self.list_url,
            {"stock_status": "IN_STOCK"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_filter_out_of_stock_products(self):
        self.product.stock_quantity = 0
        self.product.save()

        response = self.client.get(
            self.list_url,
            {"stock_status": "OUT_OF_STOCK"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    # AUTHENTICATION

    def test_unauthenticated_user_cannot_access_products(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            403
        )
