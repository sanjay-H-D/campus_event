"""Razorpay gateway adapter. Secrets never leave this server-side module."""

import razorpay

from ..config import get_setting
from .exceptions import ConfigurationError


class RazorpayGateway:
    def __init__(self) -> None:
        key_id = get_setting("RAZORPAY_KEY_ID")
        key_secret = get_setting("RAZORPAY_KEY_SECRET")
        if not key_id or not key_secret:
            raise ConfigurationError(
                "Razorpay test credentials are not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET."
            )
        self.key_id = key_id
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(self, amount_paise: int, receipt: str) -> dict:
        return self.client.order.create(
            data={"amount": amount_paise, "currency": "INR", "receipt": receipt, "payment_capture": 1}
        )
