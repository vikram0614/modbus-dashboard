# config.py

MODE = "tcp"  # "tcp" or "rtu"

# For Modbus TCP
TCP_DEVICES = [
    # Each device: (name, host, port, unit_id)
    ("Device A", "192.168.1.10", 502, 1),
    ("Device B", "192.168.1.11", 502, 1),
]

# For Modbus RTU (serial)
RTU_PORT = "/dev/ttyUSB0"
RTU_BAUDRATE = 9600
RTU_BYTESIZE = 8
RTU_PARITY = "N"
RTU_STOPBITS = 1
RTU_TIMEOUT = 1.0

RTU_DEVICES = [
    # Each device: (name, unit_id)
    ("Device 1", 1),
    ("Device 2", 2),
]

# Default registers (holding register addresses)
DEFAULT_REGISTERS = [0x2000]  # change to your common default
POLL_INTERVAL_SEC = 0.5
