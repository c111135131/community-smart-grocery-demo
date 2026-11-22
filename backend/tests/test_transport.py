from app.gateway.transport import MatterTransportAdapter, SimulatedMatterThreadTransport


def test_transport_delivers_bytes_unchanged_and_returns_handler_result():
    seen = []
    t = SimulatedMatterThreadTransport(lambda f: seen.append(f) or "ok")
    assert t.send(b"\x01\x02") == "ok"
    assert seen == [b"\x01\x02"]


def test_transport_does_not_validate_so_malformed_frames_reach_gateway():
    seen = []
    SimulatedMatterThreadTransport(seen.append).send(b"")
    assert seen == [b""]


def test_transport_is_clearly_labelled_as_simulation():
    assert isinstance(SimulatedMatterThreadTransport(lambda f: None), MatterTransportAdapter)
    assert "SIMULATED" in SimulatedMatterThreadTransport.description
