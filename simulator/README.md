# Simulator

The IoT device simulator lives inside the backend package so the API can call it
directly: `backend/app/simulator/` (`DeviceSimulator` builds 16-byte packets; it has
no knowledge of prices, carts or inventory).

Packet codec, validator and the simulated Matter-over-Thread transport are in
`backend/app/gateway/`.

Generate a packet without a database:

```bash
cd backend
python -m app.simulator --device 1 --seq 1 --command ADD_ITEM --product 101 --weight 320
```

There is no real Thread network or hardware; the transport is a software simulation.
