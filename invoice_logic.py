"""Shared invoice calculations and preliminary Malaysian e-Invoice field checks.

This is NOT a MyInvois API validator. No LHDN submission is implemented.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

CENT = Decimal('0.01')
TAX_TYPES = {
    '01': 'Sales Tax',
    '02': 'Service Tax',
    '03': 'Tourism Tax',
    '04': 'High-Value Goods Tax',
    '05': 'Sales Tax on Low Value Goods',
    '06': 'Not Applicable',
    'E': 'Tax Exemption',
}
CURRENCIES = ['MYR', 'USD', 'SGD', 'EUR', 'GBP', 'AUD']
ID_TYPES = ['BRN', 'NRIC', 'PASSPORT', 'ARMY']


def money(value) -> Decimal:
    """Use decimal arithmetic instead of floats for financial amounts."""
    try:
        out = Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError):
        raise ValueError('A money field is not a number.') from None
    if not out.is_finite():
        raise ValueError('Amounts must be finite numbers.')
    return out.quantize(CENT, rounding=ROUND_HALF_UP)


def totals(items: list[dict], discount_percent=0, shipping_fee=0) -> dict[str, Decimal]:
    """Calculate money rounded at the item level; tax after discount allocation.

    Shipping is an invoice-level charge (not taxed automatically). Tax treatment
    depends on the underlying supply and must be reviewed by the issuer.
    """
    discount_rate = Decimal(str(discount_percent or 0))
    if not (0 <= discount_rate <= 100):
        raise ValueError('Discount must be between 0% and 100%.')
    shipping = money(shipping_fee)
    if shipping < 0:
        raise ValueError('Additional charges cannot be negative.')
    subtotal = Decimal('0.00')
    discount = Decimal('0.00')
    tax = Decimal('0.00')
    for item in items:
        qty = Decimal(str(item.get('quantity', 0) or 0))
        price = money(item.get('unit_price', 0))
        rate = Decimal(str(item.get('tax_rate', 0) or 0))
        tax_type = str(item.get('tax_type') or '06')
        if not qty.is_finite() or qty <= 0 or price < 0 or not rate.is_finite() or not (0 <= rate <= 100):
            raise ValueError('Each item needs positive quantity, nonnegative price and tax rate 0–100%.')
        if tax_type not in TAX_TYPES:
            raise ValueError('Unknown LHDN tax type code.')
        if tax_type in ('06', 'E') and rate != 0:
            raise ValueError('Not Applicable / Exemption rows must have a 0% applied rate in this prototype.')
        line = (qty * price).quantize(CENT, rounding=ROUND_HALF_UP)
        line_discount = (line * discount_rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        line_tax = ((line - line_discount) * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal += line
        discount += line_discount
        tax += line_tax
    return {
        'subtotal': money(subtotal), 'discount': money(discount),
        'net': money(subtotal - discount), 'shipping': shipping,
        'tax': money(tax), 'total': money(subtotal - discount + shipping + tax),
    }


def validate_invoice(invoice: dict, items: list[dict], supplier: dict, *, for_issue=False) -> tuple[list[str], list[str]]:
    """Basic local checks only (not tax authority validation)."""
    errors, warnings = [], []
    if not str(invoice.get('invoice_number', '')).strip():
        errors.append('Invoice number is required.')
    if len(str(invoice.get('invoice_number', ''))) > 50:
        errors.append('Invoice number must be at most 50 characters.')
    if not str(invoice.get('client_name', '')).strip():
        errors.append('Buyer name is required.')
    if not items:
        errors.append('Add at least one line item.')
    for idx, item in enumerate(items, 1):
        if not str(item.get('description', '')).strip():
            errors.append(f'Item {idx}: description is required.')
        if len(str(item.get('description', ''))) > 300:
            errors.append(f'Item {idx}: description must be at most 300 characters.')
        code = str(item.get('classification_code') or '')
        if not re.fullmatch(r'\d{3}', code):
            errors.append(f'Item {idx}: classification must be a three-digit code (e.g. 022).')
        try:
            totals([item])
        except ValueError as exc:
            errors.append(f'Item {idx}: {exc}')
    try:
        issue = date.fromisoformat(str(invoice.get('issue_date', '')))
        due = date.fromisoformat(str(invoice.get('due_date', '')))
        if due < issue:
            errors.append('Due date cannot be earlier than issue date.')
    except ValueError:
        errors.append('Issue date and due date must be valid dates.')
    if invoice.get('currency') not in CURRENCIES:
        errors.append('Choose a supported ISO currency.')
    if invoice.get('currency') != 'MYR':
        try:
            if Decimal(str(invoice.get('exchange_rate') or 0)) <= 0:
                errors.append('An exchange rate to MYR is required for foreign-currency invoices.')
        except InvalidOperation:
            errors.append('Exchange rate must be a positive number.')
    if for_issue:
        required_supplier = {
            'name': 'business name', 'tin': 'TIN', 'id_type': 'identity type',
            'id_number': 'identity/registration number', 'msic': 'MSIC',
            'activity': 'business activity', 'address': 'address',
            'city': 'city', 'postcode': 'post code', 'state_code': 'state code',
            'phone': 'telephone', 'country_code': 'country code',
        }
        missing = [label for key, label in required_supplier.items() if not str(supplier.get(key) or '').strip()]
        if missing:
            errors.append('Complete supplier profile in Settings: ' + ', '.join(missing) + '.')
        buyer_required = {
            'client_tin': 'TIN', 'client_id_type': 'ID type',
            'client_id_number': 'ID number', 'client_address': 'address',
            'client_city': 'city', 'client_postcode': 'postcode',
            'client_state_code': 'state code', 'client_phone': 'telephone',
            'client_country_code': 'country code',
        }
        missing = [label for key, label in buyer_required.items() if not str(invoice.get(key) or '').strip()]
        if missing:
            errors.append('Complete buyer details: ' + ', '.join(missing) + '.')
    # Local format checks only; authoritative TIN / BRN matching requires LHDN APIs.
    for label, phone in [('Supplier', supplier.get('phone')), ('Buyer', invoice.get('client_phone'))]:
        if for_issue and phone and not re.fullmatch(r'\+?[0-9]{8,20}', str(phone)):
            errors.append(f'{label} phone must contain 8–20 digits, optionally prefixed by +.')
    for label, email in [('Supplier', supplier.get('email')), ('Buyer', invoice.get('client_email'))]:
        if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', str(email)):
            errors.append(f'{label} email address format is invalid.')
    if for_issue and invoice.get('client_country_code') == 'MYS':
        postcode = str(invoice.get('client_postcode', ''))
        if postcode and not re.fullmatch(r'\d{5}', postcode):
            errors.append('Malaysian buyer postcode must contain five digits.')
    if for_issue and supplier.get('country_code') == 'MYS':
        postcode = str(supplier.get('postcode', ''))
        if postcode and not re.fullmatch(r'\d{5}', postcode):
            errors.append('Malaysian supplier postcode must contain five digits.')
    if invoice.get('shipping_fee') and money(invoice['shipping_fee']) > 0:
        warnings.append('Review the tax treatment of the additional fee before any official submission.')
    if any(x.get('tax_type') == 'E' for x in items):
        warnings.append('Tax exemptions require applicable supporting justification and official MyInvois treatment.')
    warnings.append('Local checks do not constitute LHDN validation; submission, UUID, official QR and digital signature are not implemented.')
    return errors, warnings


def fmt(amount, currency='MYR') -> str:
    return f"{'RM' if currency == 'MYR' else currency} {money(amount):,.2f}"
