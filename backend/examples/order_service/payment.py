"""A fake payment gateway.

The card token is passed as an attribute on purpose: the tracer must
redact it (its key contains "card"), which the tests check.
"""

import time
import uuid

from examples.order_service.errors import PaymentDeclinedError
from tracer import set_attribute, traced

DECLINED_TOKEN = "tok_declined"


class PaymentGateway:
    @traced("payment.charge")
    def charge(self, card_token: str, amount_cents: int) -> str:
        set_attribute("amount_cents", amount_cents)
        set_attribute("card_token", card_token)  # redacted by the tracer
        time.sleep(0.015)
        if card_token == DECLINED_TOKEN:
            raise PaymentDeclinedError("Card was declined by the issuer")
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        set_attribute("payment_id", payment_id)
        return payment_id
