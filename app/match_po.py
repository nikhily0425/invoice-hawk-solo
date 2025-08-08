def two_way_match(payload: dict, price_tol=0.02, qty_tol=0.01) -> dict:
    # TODO: replace with NetSuite lookup. Stub PO:
    po = {"po_number": payload["po_number"], "lines": [{"sku":"KB-101","qty":10,"unit_price":99.5}]}
    inv = payload["lines"][0]; pol = po["lines"][0]
    price_ok = abs(inv["unit_price"]-pol["unit_price"]) <= pol["unit_price"]*price_tol
    qty_ok = abs(inv["qty"]-pol["qty"]) <= max(1, pol["qty"]*qty_tol)
    return {"matched": bool(price_ok and qty_ok), "price_ok": price_ok, "qty_ok": qty_ok}
