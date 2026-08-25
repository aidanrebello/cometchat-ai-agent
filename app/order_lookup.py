import json
import re
from pathlib import Path


ORDERS_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "orders.json"
)


def load_orders():
    """
    Load the mock order dataset.

    The full dataset stays inside the application.
    Only a sanitized single-order result is returned
    to the agent.
    """

    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("orders", [])


def normalize_order_id(order_id: str):
    """
    Normalize harmless input differences such as:

    ORD-1007
    ord-1007
    ' ORD-1007 '
    """

    if not isinstance(order_id, str):
        return None

    order_id = order_id.strip().upper()

    if not order_id:
        return None

    return order_id


def is_valid_order_id(order_id: str):
    """
    Validate the expected mock order ID format.
    """

    return bool(
        re.fullmatch(
            r"ORD-\d{4}",
            order_id
        )
    )


def lookup_order(order_id: str):
    """
    Safely look up one order.

    IMPORTANT:
    This function never returns:
    - customer email
    - shipping address
    - internal notes
    - risk scores
    - internal support tags

    Only customer-safe fields are returned.
    """

    normalized_id = normalize_order_id(order_id)

    if normalized_id is None:

        return {
            "found": False,
            "error": "missing_order_id"
        }

    if not is_valid_order_id(normalized_id):

        return {
            "found": False,
            "error": "invalid_order_id"
        }

    orders = load_orders()

    order = next(
        (
            item
            for item in orders
            if item.get("order_id") == normalized_id
        ),
        None
    )

    if order is None:

        return {
            "found": False,
            "error": "order_not_found",
            "order_id": normalized_id
        }

    status = order.get("status")

    # --------------------------------------------------------
    # CUSTOMER-SAFE RESULT
    # --------------------------------------------------------

    result = {
        "found": True,
        "order_id": normalized_id,
        "status": status,
        "status_updated_at": order.get(
            "status_updated_at"
        ),
        "items": [
            {
                "name": item.get("name"),
                "quantity": item.get("quantity"),
                "final_sale": item.get("final_sale")
            }
            for item in order.get("items", [])
        ],
        "customer_safe_message": order.get(
            "customer_safe_message"
        )
    }

    # --------------------------------------------------------
    # DELIVERY INFORMATION
    # --------------------------------------------------------
    #
    # Only expose shipping/delivery information when the
    # current status makes it relevant.
    #
    # Cancelled and returned orders must not expose stale
    # shipping/ETA fields.
    # --------------------------------------------------------

    if status in {
        "shipped",
        "delayed",
        "exception"
    }:

        result["carrier"] = order.get("carrier")

        result["tracking_number"] = order.get(
            "tracking_number"
        )

        estimated_delivery = order.get(
            "estimated_delivery"
        )

        if estimated_delivery:
            result["estimated_delivery"] = (
                estimated_delivery
            )

    # --------------------------------------------------------
    # DELIVERED
    # --------------------------------------------------------

    elif status == "delivered":

        delivered_at = order.get(
            "delivered_at"
        )

        if delivered_at:

            result["delivered_at"] = delivered_at

    # --------------------------------------------------------
    # RETURNED
    # --------------------------------------------------------

    elif status == "returned":

        # Deliberately do not expose old carrier,
        # tracking or ETA fields.
        #
        # The customer-safe message is sufficient.
        pass

    # --------------------------------------------------------
    # CANCELLED
    # --------------------------------------------------------

    elif status == "cancelled":

        # Deliberately do not expose stale carrier,
        # tracking or estimated-delivery fields.
        pass

    return result