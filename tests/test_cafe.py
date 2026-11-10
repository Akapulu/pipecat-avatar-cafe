import asyncio
from types import SimpleNamespace


class FakeOutput:
    def __init__(self):
        self.sent = []

    async def send_message(self, frame):
        self.sent.append(frame.message)


class FakeTransport:
    def __init__(self):
        self.out = FakeOutput()

    def output(self):
        return self.out


def call(order, tool, **arguments):
    results = []

    async def result_callback(result):
        results.append(result)

    asyncio.run(getattr(order, tool)(SimpleNamespace(arguments=arguments, result_callback=result_callback)))
    return results[0]


def test_every_tool_has_a_handler():
    from bot import TOOLS, CafeOrder

    for tool in TOOLS.standard_tools:
        assert callable(getattr(CafeOrder, tool.name))


def test_order_flow_sends_page_events():
    from bot import CafeOrder

    transport = FakeTransport()
    order = CafeOrder(transport)
    assert "Vegan" in call(order, "filter_menu", tag="vegan")
    assert "Total $11.00" in call(order, "add_to_order", item_id="oat-latte", quantity=2)
    assert "Total $15.00" in call(order, "add_to_order", item_id="banana-bread", quantity=1)
    assert "Total $4.00" in call(order, "remove_from_order", item_id="oat-latte")
    assert "Order placed for Sam" in call(order, "place_order", name="Sam")
    events = [m["event"] for m in transport.out.sent]
    assert events == ["filter", "highlight", "order", "highlight", "order", "order", "placed"]
    assert all(m["label"] == "cafe" for m in transport.out.sent)


def test_place_order_refuses_empty():
    from bot import CafeOrder

    order = CafeOrder(FakeTransport())
    assert "empty" in call(order, "place_order", name="Sam")


def test_gift_card_takes_balance_off_total():
    from bot import CafeOrder

    transport = FakeTransport()
    order = CafeOrder(transport)
    call(order, "add_to_order", item_id="oat-latte", quantity=2)
    assert "not a valid" in call(order, "apply_gift_card", code="STARBUCKS-1")
    assert "Total $0.00" in call(order, "apply_gift_card", code="sunday 2517".replace(" ", "-"))
    assert transport.out.sent[-1] == {"label": "cafe", "event": "order", "lines": {"oat-latte": 2}, "gift": 25.0, "total": 0.0}


def test_look_at_camera_needs_a_caller():
    from bot import CafeOrder

    assert "not on" in call(CafeOrder(FakeTransport()), "look_at_camera", question="gift card?")
