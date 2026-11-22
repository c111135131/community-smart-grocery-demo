"""CLI: build a packet and print its hex without needing the API or database.

    python -m app.simulator --device 1 --seq 1 --command ADD_ITEM --product 101 --weight 320

The printed hex can be pasted into the "send raw packet" box of the web UI.
"""
import argparse

from app.core.config import get_settings
from app.gateway.packet import Command, PacketEncodeError, decode_packet
from app.simulator.device import DeviceSimulator


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a 16-byte demo packet.")
    parser.add_argument("--device", type=int, default=1)
    parser.add_argument("--seq", type=int, required=True, help="sequence number (0..65535)")
    parser.add_argument("--command", choices=[c.name for c in Command], default="ADD_ITEM")
    parser.add_argument("--product", type=int, required=True, help="product code, e.g. 101")
    parser.add_argument("--weight", type=int, required=True, help="weight in grams")
    args = parser.parse_args()

    key = get_settings().iot_secret_key.encode()
    try:
        frame = DeviceSimulator(args.device, key).build_packet(
            sequence=args.seq,
            command=Command[args.command],
            product_code=args.product,
            weight_grams=args.weight,
        )
    except PacketEncodeError as exc:  # a value does not fit its packet field
        parser.error(str(exc))
    print("packet_hex :", frame.hex().upper())
    print("length     :", len(frame), "bytes")
    print("decoded    :", decode_packet(frame, key))
    print("note       : educational XOR/hash check only, not cryptographically secure")


if __name__ == "__main__":
    main()
