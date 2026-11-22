"""Orchestrates the IoT flow: simulator -> transport -> gateway -> cart, with audit.

    DeviceSimulator --16 bytes--> SimulatedMatterThreadTransport --> gateway validator
        --> NormalizedIoTEvent --> cart_service --> audit row (iot_events)

Sequence rule (documented assumption): the device's last_sequence_number is updated
as soon as the packet passes ALL gateway checks, even if the cart later rejects the
request for a business reason (unknown product, not enough stock, ...). A packet
that fails any gateway check never advances the sequence.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.gateway.events import to_normalized_event
from app.gateway.packet import Command, command_name
from app.gateway.transport import SimulatedMatterThreadTransport
from app.gateway.validator import ValidationReport, validate_frame
from app.models import Cart, CartItem, Device, IotEvent, Product, Resident
from app.schemas.iot import (
    CartEventRequest,
    CartEventResult,
    DeviceOut,
    IotEventOut,
    ParsedPacketOut,
    ValidationOut,
)
from app.services import cart_service
from app.services.resident_service import ResidentNotFoundError
from app.simulator.device import DeviceSimulator

MAX_SEQUENCE = 0xFFFF


class DeviceNotFoundError(Exception):
    """The simulated device does not exist."""


class SequenceExhaustedError(Exception):
    """16-bit sequence space is used up (wrap-around is out of scope for the demo)."""


def _secret() -> bytes:
    return get_settings().iot_secret_key.encode()


def _event_id(row_id: int) -> str:
    return f"evt-{row_id}"


def _ensure_resident(db: Session, resident_id: int) -> None:
    if db.get(Resident, resident_id) is None:
        raise ResidentNotFoundError(resident_id)


def _lock_device(db: Session, device_id: int) -> Device | None:
    """Fetch a device row with a row lock so concurrent events cannot race on the sequence."""
    return db.scalar(select(Device).where(Device.id == device_id).with_for_update())


def _handle_frame(db: Session, resident_id: int, frame: bytes) -> CartEventResult:
    """Gateway entry point: validate, update sequence, apply to cart, audit, commit."""
    devices: dict[int, Device] = {}

    def last_sequence(device_id: int) -> int | None:
        device = _lock_device(db, device_id)
        if device is None:
            return None
        devices[device_id] = device
        return device.last_sequence_number

    try:
        report = validate_frame(frame, secret_key=_secret(), last_sequence_lookup=last_sequence)

        rejection_code: str | None = report.rejection_code.value if report.rejection_code else None
        rejection_reason = report.rejection_reason
        cart_valid: bool | None = None

        if report.accepted:
            packet = report.packet
            assert packet is not None
            # Whole packet validated: consume the sequence number.
            devices[packet.device_id].last_sequence_number = packet.sequence
            try:
                cart_service.apply_event(db, resident_id, to_normalized_event(packet))
                cart_valid = True
            except cart_service.CartRejection as rej:
                cart_valid = False
                rejection_code, rejection_reason = rej.code.value, rej.message

        accepted = rejection_code is None
        packet = report.packet
        row = IotEvent(
            resident_id=resident_id,
            # Only link a device FK when that device really exists.
            device_id=packet.device_id if packet and packet.device_id in devices else None,
            sequence_number=packet.sequence if packet else None,
            command=command_name(packet.command) if packet else None,
            product_code=packet.product_code if packet else None,
            weight_grams=packet.weight_grams if packet else None,
            packet_hex=frame.hex().upper(),
            validation_status="ACCEPTED" if accepted else "REJECTED",
            rejection_reason=None if accepted else f"{rejection_code}: {rejection_reason}",
        )
        db.add(row)
        db.flush()
        event_id = _event_id(row.id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return CartEventResult(
        accepted=accepted,
        event_id=event_id,
        transport=SimulatedMatterThreadTransport.description,
        packet_hex=frame.hex().upper(),
        packet=_packet_out(report),
        validation=_validation_out(report, cart_valid),
        rejection_code=rejection_code,
        rejection_reason=rejection_reason,
        cart=cart_service.get_cart(db, resident_id),
    )


def _packet_out(report: ValidationReport) -> ParsedPacketOut | None:
    p = report.packet
    if p is None:
        return None
    return ParsedPacketOut(
        device_id=p.device_id,
        sequence_number=p.sequence,
        command=command_name(p.command),
        product_code=p.product_code,
        weight_grams=p.weight_grams,
        flags=p.flags,
    )


def _validation_out(report: ValidationReport, cart_valid: bool | None) -> ValidationOut:
    return ValidationOut(
        length_valid=report.length_valid,
        header_valid=report.header_valid,
        command_valid=report.command_valid,
        xor_valid=report.xor_valid,
        hash_valid=report.hash_valid,
        check_code_valid=report.check_code_valid,
        device_known=report.device_known,
        sequence_valid=report.sequence_valid,
        fields_valid=report.fields_valid,
        cart_valid=cart_valid,
    )


def _send_through_transport(db: Session, resident_id: int, frame: bytes) -> CartEventResult:
    transport = SimulatedMatterThreadTransport(lambda f: _handle_frame(db, resident_id, f))
    return transport.send(frame)


def submit_simulated_event(
    db: Session, resident_id: int, request: CartEventRequest
) -> CartEventResult:
    """Simulate a device event: pick the next sequence, encode 16 bytes, send via gateway.

    The simulated device's next sequence is (last accepted + 1), keeping it in sync
    with the gateway even after a backend restart.
    """
    _ensure_resident(db, resident_id)
    device = _lock_device(db, request.device_id)
    if device is None:
        db.rollback()
        raise DeviceNotFoundError(request.device_id)
    sequence = device.last_sequence_number + 1
    if sequence > MAX_SEQUENCE:
        db.rollback()
        raise SequenceExhaustedError(request.device_id)

    frame = DeviceSimulator(request.device_id, _secret()).build_packet(
        sequence=sequence,
        command=Command[request.command],
        product_code=request.product_code,
        weight_grams=request.weight_grams,
    )
    return _send_through_transport(db, resident_id, frame)


def submit_raw_packet(db: Session, resident_id: int, packet_hex: str) -> CartEventResult:
    """Send an arbitrary frame (replayed / tampered / malformed) through the same gateway."""
    _ensure_resident(db, resident_id)
    return _send_through_transport(db, resident_id, bytes.fromhex(packet_hex))


class ProductNotFoundError(Exception):
    """No product with the given id."""


class ItemNotInCartError(Exception):
    """The product exists but the resident's cart does not hold it."""


def remove_cart_item(
    db: Session, resident_id: int, product_id: int, device_id: int
) -> list[CartEventResult]:
    """Remove a whole product line through the SAME gateway path as any other event.

    The line's weight is sent as one or more REMOVE_ITEM packets, each at most the
    product's per-event maximum, so every packet is validated, sequenced and audited
    exactly like a device event. Stops at the first rejected packet.
    """
    _ensure_resident(db, resident_id)
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)
    item = db.scalar(
        select(CartItem)
        .join(Cart, CartItem.cart_id == Cart.id)
        .where(Cart.resident_id == resident_id, CartItem.product_id == product_id)
    )
    if item is None:
        raise ItemNotInCartError(product_id)

    remaining = item.weight_grams
    results: list[CartEventResult] = []
    while remaining > 0:
        chunk = min(remaining, product.max_weight_grams)
        result = submit_simulated_event(
            db,
            resident_id,
            CartEventRequest(
                device_id=device_id,
                command="REMOVE_ITEM",
                product_code=product.product_code,
                weight_grams=chunk,
            ),
        )
        results.append(result)
        if not result.accepted:
            break
        remaining -= chunk
    return results


def list_iot_events(db: Session, limit: int = 50) -> list[IotEventOut]:
    rows = db.scalars(select(IotEvent).order_by(IotEvent.id.desc()).limit(limit))
    return [
        IotEventOut(
            id=r.id,
            event_id=_event_id(r.id),
            resident_id=r.resident_id,
            device_id=r.device_id,
            sequence_number=r.sequence_number,
            command=r.command,
            product_code=r.product_code,
            weight_grams=r.weight_grams,
            packet_hex=r.packet_hex,
            validation_status=r.validation_status,
            rejection_reason=r.rejection_reason,
            created_at=r.created_at,
        )
        for r in rows
    ]


def list_devices(db: Session) -> list[DeviceOut]:
    rows = db.scalars(select(Device).order_by(Device.id))
    return [
        DeviceOut(
            id=d.id,
            device_code=d.device_code,
            description=d.description,
            last_sequence_number=d.last_sequence_number,
        )
        for d in rows
    ]
