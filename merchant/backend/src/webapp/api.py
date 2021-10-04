from dataclasses import asdict
from datetime import datetime
import os
from uuid import UUID
import uuid

from flask import Blueprint, request
from requests import HTTPError
import requests
import json

import store.products
from store.orders import Order, OrderItem, get_order_details
from vasp_client import vasp_client
from vasp_client.types import PaymentStatus

from .schemas import (
    CheckoutRequest,
    CheckoutResponse,
    ProductList,
    OrderDetails,
    ProductOrder,
    Product,
)
from .strict_schema_view import (
    StrictSchemaView,
    response_definition,
    body_parameter,
    path_str_param,
    path_uuid_param,
)
import logging

api = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


def order_item_to_product_order(item: OrderItem) -> ProductOrder:
    return ProductOrder(
        quantity=item.quantity,
        product=Product.from_dict(
            store.products.get_product_details(item.gtin).to_dict()
        ),
    )


class ApiView(StrictSchemaView):
    pass


class ProductListView(ApiView):
    summary = "Returns list of products"
    parameters = []
    responses = {
        200: response_definition("list of products", schema=ProductList.schema),
    }

    def get(self):
        products = store.products.get_products_list()
        product_list = ProductList(products=list(products))

        return product_list.to_dict(), 200


class CheckoutView(ApiView):
    summary = "Initiate new payment process for a single product"
    parameters = [
        body_parameter(CheckoutRequest),
    ]
    responses = {
        200: response_definition(
            "Payment ID and payment form URL", schema=CheckoutResponse
        ),
    }

    def post(self):
        purchase_request = CheckoutRequest.from_dict(request.json)

        items = [
            OrderItem(gtin=item.gtin, quantity=item.quantity)
            for item in purchase_request.items
        ]
        order = store.orders.create_order(items)
        order_id = str(order.order_id)

        PAYMENT_VASP_URL = os.getenv("PAYMENT_VASP_URL", "http://127.0.0.1:7000")
        VASP_TOKEN = os.getenv("VASP_TOKEN")
        MERCHANT_URL = os.getenv("MERCHANT_URL", "http://localhost:8000/")

        logger.info(f"PAYMENT_VASP_URL={PAYMENT_VASP_URL}")
        logger.info(f"VASP_TOKEN={VASP_TOKEN}")
        logger.info(f"MERCHANT_URL={MERCHANT_URL}")

        redirect_url = f"{MERCHANT_URL}order/{order_id}"
        request_body = {
            "redirectUrl": redirect_url,
            "scope": {
                "requestCurrency": {
                    "amount": order.total_price,
                    "fractionDigits": 6,
                    "currency": order.currency,
                },
                "processingCurrency": "XUS",
                "expirationTimestamp": int(datetime.now().timestamp()) + 60 * 10,
            },
            "action": "CHARGE",
            "reconciliationId": order_id,
        }

        jsonkey = {"apiKey": VASP_TOKEN}

        r = requests.post(url=f"{PAYMENT_VASP_URL}/auth/login", json=jsonkey)
        response = r.json()

        logger.info(response)
        auth_token = response["authToken"]
        headers = {"Authorization": f"Bearer {auth_token}"}

        rpayment = requests.post(
            f"{PAYMENT_VASP_URL}/payments", json=request_body, headers=headers
        )
        payment = rpayment.json()
        logger.info(payment)

        payment_id = payment["payment"]["paymentId"]
        order.vasp_payment_reference = payment_id
        open(f"/tmp/{order_id}", "w").write(order.to_json())

        checkout_data = payment["payment"]["data"]
        for wl in checkout_data["walletLinks"]:
            wl["link"] += f"&demo=false&redirectUrl={redirect_url}"

        result = {
            "order_id": order_id,
            "qr": checkout_data["qr"],
            "deepLink": checkout_data["deepLink"],
            "walletLinks": checkout_data["walletLinks"],
        }
        logger.info(result)

        return (
            result,
            200,
        )


class OrderDetailsView(ApiView):
    summary = "Returns payment details"
    parameters = [
        path_str_param(
            name="order_id", description="Get payment status", required=True
        ),
    ]
    responses = {
        200: response_definition("Log of payment events", schema=OrderDetails.schema),
    }

    def get(self, order_id):
        order = get_order_details(order_id)
        if order is None:
            return "Unknown order", 404

        db_content = open(f"/tmp/{order_id}", "r").read()
        logger.info("db content")
        logger.info(db_content)
        order = Order.from_json(db_content)
        vasp_payment_id = order.vasp_payment_reference

        PAYMENT_VASP_URL = os.getenv("PAYMENT_VASP_URL", "http://127.0.0.1:7000")
        VASP_TOKEN = os.getenv("VASP_TOKEN")

        jsonkey = {"apiKey": VASP_TOKEN}

        r = requests.post(url=f"{PAYMENT_VASP_URL}/auth/login", json=jsonkey)
        response = r.json()

        logger.info(response)
        auth_token = response["authToken"]
        headers = {"Authorization": f"Bearer {auth_token}"}

        rpayment = requests.get(
            f"{PAYMENT_VASP_URL}/payments/{vasp_payment_id}", headers=headers
        )
        payment = rpayment.json()
        logger.info(payment)

        order_details = OrderDetails(
            order_id=str(order.order_id),
            created_at=order.created_at,
            vasp_payment_reference=order.vasp_payment_reference,
            total_price=order.total_price,
            currency=order.currency,
            products=[order_item_to_product_order(item) for item in order.items],
            payment_status={
                "status": payment["payment"]["state"],
                "merchant_address": "",
                "can_payout": True,
                "can_refund": True,
                "events": [],
                "chain_txs": [],
            },
        )

        return order_details.to_dict(), 200


class PaymentStatusView(ApiView):
    summary = "Get payment status"
    parameters = [
        path_str_param(name="order_id", description="Get payment status", required=True)
    ]

    responses = {
        200: response_definition("Payment Status", schema=PaymentStatus.schema),
    }

    def get(self, order_id: str):
        try:
            payment_status = vasp_client.get_payment_status(
                merchant_reference_id=order_id
            )
            return payment_status.to_dict(), 200
        except HTTPError as e:
            raise e


class PayoutView(ApiView):
    summary = "Request pay-out for a specific payment"
    parameters = [
        path_uuid_param("payment_id", "VASP payment ID"),
    ]

    def post(self, payment_id: UUID):
        vasp_client.payout(payment_id)
        return {"status": "OK"}, 200


class RefundView(ApiView):
    summary = "Refund specific payment"
    parameters = [
        path_uuid_param("payment_id", "VASP payment ID"),
    ]

    def post(self, payment_id: UUID):
        vasp_client.refund(payment_id)
        return {"status": "OK"}, 200


api.add_url_rule(
    rule="/products",
    view_func=ProductListView.as_view("product_list"),
    methods=["GET"],
)

api.add_url_rule(
    rule="/payments",
    view_func=CheckoutView.as_view("checkout"),
    methods=["POST"],
)

api.add_url_rule(
    rule="/payments/<uuid:payment_id>/payout",
    view_func=PayoutView.as_view("payout"),
    methods=["POST"],
)

api.add_url_rule(
    rule="/payments/<uuid:payment_id>/refund",
    view_func=RefundView.as_view("refund"),
    methods=["POST"],
)

api.add_url_rule(
    rule="/orders/<uuid:order_id>",
    view_func=OrderDetailsView.as_view("order_details"),
    methods=["GET"],
)

api.add_url_rule(
    rule="/orders/<uuid:order_id>/payment",
    view_func=PaymentStatusView.as_view("payment_status"),
    methods=["GET"],
)
