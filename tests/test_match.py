from app.match_po import two_way_match

def test_two_way_match_pass():
    payload = {
        "po_number":"45001234",
        "lines":[{"sku":"KB-101","qty":10,"unit_price":99.5}]
    }
    res = two_way_match({
        "po_number":"45001234",
        "lines":[{"sku":"KB-101","qty":10,"unit_price":99.5}]
    })
    assert res["matched"] is True
