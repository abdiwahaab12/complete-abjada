"""Order payment_status sync and financial validation (customer orders)."""
from __future__ import annotations

from typing import Optional, Tuple

EPS = 1e-6

# Must match routes.orders.PRODUCT_ORDER_CUSTOMER_PHONE — walk-in product sales placeholder.
PRODUCT_ORDER_PLACEHOLDER_PHONE = '__product_order__'


def order_is_product_placeholder_sale(order) -> bool:
    """
    Orders with no real customer use a system Customer row (full name 'Product order').
    Those are retail / POS style sales; they do not belong in tailor accounts receivable.
    """
    if order is None:
        return False
    try:
        c = order.customer
    except Exception:
        c = None
    if c is None:
        return False
    return getattr(c, 'phone', None) == PRODUCT_ORDER_PLACEHOLDER_PHONE


def compute_payment_status(total_price: float, advance_paid: float) -> str:
    """Derive paid | unpaid | partial from amounts."""
    tp = float(total_price or 0)
    ap = float(advance_paid or 0)
    if tp <= EPS:
        return 'unpaid'
    if ap >= tp - EPS:
        return 'paid'
    if ap <= EPS:
        return 'unpaid'
    return 'partial'


def sync_order_payment_status(order) -> None:
    """Persist payment_status from total_price and advance_paid."""
    if order is None:
        return
    order.payment_status = compute_payment_status(order.total_price, order.advance_paid)


def validate_order_amounts(total_price: float, advance_paid: float) -> Tuple[bool, Optional[str]]:
    """Ensure order total = paid + balance (paid <= total, non-negative)."""
    tp = float(total_price or 0)
    ap = float(advance_paid or 0)
    if tp < -EPS or ap < -EPS:
        return False, 'Amounts cannot be negative'
    if ap > tp + EPS:
        return False, 'Paid amount cannot exceed order total'
    balance = tp - ap
    if balance < -EPS:
        return False, 'Order total must equal paid amount plus remaining balance'
    return True, None


def order_is_accounts_receivable(order) -> bool:
    """
    AR rows: tailor/customer orders still owing (unpaid or partial). Fully paid
    orders count as received. Walk-in 'Product order' placeholder sales are
    excluded from this report (paid at sale; not AR).
    """
    if order is None or getattr(order, 'status', None) == 'cancelled':
        return False
    if order_is_product_placeholder_sale(order):
        return False
    tp = float(order.total_price or 0)
    ap = float(order.advance_paid or 0)
    due = max(0.0, round(tp - ap, 2))
    if due <= 0.01:
        return False
    ps = (getattr(order, 'payment_status', None) or 'unpaid').strip().lower()
    if ps == 'paid':
        return False
    return ps in ('unpaid', 'partial')


def apply_payment_status_payload(order, data: dict) -> None:
    """
    Set advance_paid from optional payment_status (paid/unpaid/partial) and advance_paid.
    Call before commit on create/update when client sends payment_status.
    """
    if not data or 'payment_status' not in data:
        return
    ps = (data.get('payment_status') or '').strip().lower()
    tp = float(order.total_price or 0)
    if ps == 'paid':
        order.advance_paid = tp
    elif ps == 'unpaid':
        order.advance_paid = 0
    elif ps == 'partial':
        if 'advance_paid' in data:
            order.advance_paid = float(data.get('advance_paid') or 0)
    sync_order_payment_status(order)
