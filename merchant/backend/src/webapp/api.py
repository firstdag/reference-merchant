from dataclasses import asdict
from uuid import UUID

from flask import Blueprint, request
from requests import HTTPError
import requests
import json

import store.products
from store.orders import OrderItem, get_order_details
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
        # payment = vasp_client.start_payment(
        #     order.total_price, order.currency, order.order_id
        # )
        # jsonpayment = {
        #     'body':{
        #         'scope': {
        #                 'requestCurrency': { 'amount': order.total_price, 'fractionDigits': 1, 'currency': order.currency },
        #                 'expirationSeconds': 3600,
        #             },
        #         'redirectUrl': 'http://example.com',
        #         'action': "AUTHORIZATION",
        #         'reconciliationId': 'an open field to store any payment related data - for the merchant use',
        #         'updateCallback': 'http://example.com',
        #             },
        #     'authorization': {
        #                     'jwt': 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJjN2YxMzM3OS04OGVjLTQ3ZjQtODNkZS0wMGE3NTg3NjI2NDMiLCJyb2xlIjoiU2VydmljZSIsIm1ldGFkYXRhIjp7Im1lcmNoYW50TmFtZSI6IlRlc3QgTWVyY2hhbnQgLSAyMDIxLTA5LTMwVDExOjM5OjQwLjc2MloifSwiaWF0IjoxNjMzMDgxOTA2LCJleHAiOjE2MzMwODU1MDZ9.MEYCIQDORfGvyd7wEEcwv34oTsLufwncYknn7xkz6CO5dvnxYAIhAJ5Qzy92uVVPMKOqkoNBMfMQydehMNmOutpZzpJPvZYY","identity":"c7f13379-88ec-47f4-83de-00a758762643', 
        #                     'jwtPayload': {
        #                         'userId': 'user',
        #                         'role': 'Merchant',
        #                         'metadata': {},
        #                                 }
        #     }
        # },

        request_body = {
            "scope": {
                "requestCurrency": {
                    "amount": order.total_price, 
                    "currency": order.currency,
                    "fractionDigits": 1,
                    }
            },
            "action": "AUTHORIZATION",
            },


        jsonkey = {
            'apiKey': 'eZ4Uk0CaOURJiEwsPlFW1hb_eItce8o2ocDz_4__lZ8'
        }

        r = requests.post(url='http://host.docker.internal:3000/api/auth/login', json=jsonkey)
        rpayment = requests.post('http://host.docker.internal:3000/api/payments', data=request_body)
        logger.info('here11')
        logger.info(r.text)

        logger.info('here12')
        logger.info(rpayment)
        logger.info(rpayment.text)


        return (
            {
                "order_id": order.order_id,
                "vasp_payment_id": payment.payment_id,
                "payment_form_url": payment.payment_form_url,
            },
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

        payment_status = vasp_client.get_payment_log(order.vasp_payment_reference)

        order_details = OrderDetails(
            order_id=str(order.order_id),
            created_at=order.created_at,
            vasp_payment_reference=order.vasp_payment_reference,
            total_price=order.total_price,
            currency=order.currency,
            products=[order_item_to_product_order(item) for item in order.items],
            payment_status=payment_status,
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
