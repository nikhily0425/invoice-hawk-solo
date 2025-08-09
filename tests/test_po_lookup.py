from invoice_hawk.lambda_functions.po_lookup.main import _compare_lines


class DummyLineItem:
    def __init__(self, quantity, price):
        self.quantity = quantity
        self.price = price


def test_compare_lines_within_tolerance():
    invoice_lines = [DummyLineItem(10, 100.0), DummyLineItem(5, 50.0)]
    po_lines = [
        {"quantity": 10.1, "price": 101.9},  # within ±1 % qty and ±2 % price
        {"quantity": 4.95, "price": 49.1},
    ]
    assert _compare_lines(invoice_lines, po_lines) is True


def test_compare_lines_outside_tolerance():
    invoice_lines = [DummyLineItem(10, 100.0)]
    po_lines = [
        {"quantity": 12, "price": 110.0},  # >1 % qty diff and >2 % price diff
    ]
    assert _compare_lines(invoice_lines, po_lines) is False