from __future__ import annotations

import threading
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request
from pymodbus.client import ModbusTcpClient, ModbusSerialClient

import config

app = Flask(__name__)

# -----------------------------
# Models / State
# -----------------------------

@dataclass
class Device:
    name: str
    unit_id: int
    host: Optional[str] = None
    port: Optional[int] = None

@dataclass
class RegisterValue:
    address: int
    value: Optional[int]
    ok: bool
    error: Optional[str] = None
    ts: float = 0.0


# Shared state
devices: List[Device] = []
registers_to_poll: List[int] = list(config.DEFAULT_REGISTERS)
latest: Dict[Tuple[str, int], Dict[int, RegisterValue]] = {}  # (device_name, unit_id) -> {addr: RegisterValue}
write_armed: bool = False

state_lock = threading.Lock()
stop_event = threading.Event()

# -----------------------------
# Modbus client handling
# -----------------------------

_tcp_clients: Dict[Tuple[str, int], ModbusTcpClient] = {}
_rtu_client: Optional[ModbusSerialClient] = None

def get_tcp_client(host: str, port: int) -> ModbusTcpClient:
    key = (host, port)
    if key not in _tcp_clients:
        c = ModbusTcpClient(host=host, port=port, timeout=1.0)
        c.connect()
        _tcp_clients[key] = c
    return _tcp_clients[key]

def get_rtu_client() -> ModbusSerialClient:
    global _rtu_client
    if _rtu_client is None:
        _rtu_client = ModbusSerialClient(
            port=config.RTU_PORT,
            baudrate=config.RTU_BAUDRATE,
            bytesize=config.RTU_BYTESIZE,
            parity=config.RTU_PARITY,
            stopbits=config.RTU_STOPBITS,
            timeout=config.RTU_TIMEOUT,
        )
        _rtu_client.connect()
    return _rtu_client

def modbus_read_holding(dev: Device, address: int) -> RegisterValue:
    try:
        if config.MODE == "tcp":
            assert dev.host is not None and dev.port is not None
            client = get_tcp_client(dev.host, dev.port)
        else:
            client = get_rtu_client()

        rr = client.read_holding_registers(address=address, count=1, slave=dev.unit_id)
        if rr is None:
            return RegisterValue(address, None, False, "No response", time.time())
        if rr.isError():
            return RegisterValue(address, None, False, str(rr), time.time())
        return RegisterValue(address, int(rr.registers[0]), True, None, time.time())
    except Exception as e:
        return RegisterValue(address, None, False, f"{type(e).__name__}: {e}", time.time())

def modbus_write_holding(dev: Device, address: int, value: int) -> RegisterValue:
    try:
        if config.MODE == "tcp":
            assert dev.host is not None and dev.port is not None
            client = get_tcp_client(dev.host, dev.port)
        else:
            client = get_rtu_client()

        wr = client.write_register(address=address, value=value, slave=dev.unit_id)
        if wr is None:
            return RegisterValue(address, None, False, "No response", time.time())
        if wr.isError():
            return RegisterValue(address, None, False, str(wr), time.time())
        return RegisterValue(address, value, True, None, time.time())
    except Exception as e:
        return RegisterValue(address, None, False, f"{type(e).__name__}: {e}", time.time())


# -----------------------------
# Polling thread
# -----------------------------

def poll_loop():
    while not stop_event.is_set():
        with state_lock:
            regs = list(registers_to_poll)
            devs = list(devices)

        for dev in devs:
            key = (dev.name, dev.unit_id)
            with state_lock:
                latest.setdefault(key, {})

            for addr in regs:
                rv = modbus_read_holding(dev, addr)
                with state_lock:
                    latest[key][addr] = rv

        time.sleep(config.POLL_INTERVAL_SEC)

def init_devices():
    global devices
    if config.MODE == "tcp":
        devices = [Device(name=n, host=h, port=p, unit_id=uid) for (n, h, p, uid) in config.TCP_DEVICES]
    else:
        devices = [Device(name=n, unit_id=uid) for (n, uid) in config.RTU_DEVICES]

    with state_lock:
        for dev in devices:
            latest.setdefault((dev.name, dev.unit_id), {})

# -----------------------------
# Routes
# -----------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/state")
def api_state():
    with state_lock:
        dev_list = [asdict(d) for d in devices]
        regs = list(registers_to_poll)
        armed = write_armed
        snap = {}
        for (dname, uid), addr_map in latest.items():
            snap_key = f"{dname}__{uid}"
            snap[snap_key] = {addr: asdict(rv) for addr, rv in addr_map.items()}
    return jsonify({"devices": dev_list, "registers": regs, "armed": armed, "latest": snap})

@app.route("/api/registers", methods=["POST", "DELETE"])
def api_registers():
    data = request.get_json(force=True)
    addr = int(data.get("address"), 0) if isinstance(data.get("address"), str) else int(data.get("address"))
    with state_lock:
        if request.method == "POST":
            if addr not in registers_to_poll:
                registers_to_poll.append(addr)
                registers_to_poll.sort()
        else:
            if addr in registers_to_poll:
                registers_to_poll.remove(addr)
    return jsonify({"ok": True, "registers": registers_to_poll})

@app.route("/api/arm", methods=["POST"])
def api_arm():
    global write_armed
    data = request.get_json(force=True)
    armed = bool(data.get("armed"))
    with state_lock:
        write_armed = armed
    return jsonify({"ok": True, "armed": write_armed})

@app.route("/api/write", methods=["POST"])
def api_write():
    data = request.get_json(force=True)
    dname = data["device_name"]
    uid = int(data["unit_id"])
    addr = int(data["address"], 0) if isinstance(data["address"], str) else int(data["address"])
    value = int(data["value"])

    with state_lock:
        if not write_armed:
            return jsonify({"ok": False, "error": "Writes are not armed"}), 403
        dev = next((d for d in devices if d.name == dname and d.unit_id == uid), None)

    if dev is None:
        return jsonify({"ok": False, "error": "Device not found"}), 404

    rv = modbus_write_holding(dev, addr, value)
    with state_lock:
        latest[(dev.name, dev.unit_id)][addr] = rv
    return jsonify({"ok": rv.ok, "result": asdict(rv)})

def main():
    init_devices()
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    finally:
        stop_event.set()

if __name__ == "__main__":
    main()
