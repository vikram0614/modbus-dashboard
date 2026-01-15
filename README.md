# modbus-dashboard

A lightweight Flask web dashboard to monitor and (optionally) write Modbus holding registers across multiple devices.

## Features
- Multi-device view (each device in its own box)
- Configurable register list (add/remove registers in the UI)
- Periodic polling with last-updated timestamps
- Optional write capability with an “ARMED” safety toggle
- JSON API endpoints for easy extension

## Tech
- Python, Flask
- pymodbus (Modbus RTU or TCP)
- Simple HTML/JS frontend (no frameworks)

## Setup

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py 

Then on a browser open: http://127.0.0.1:5000

Configure devices

Edit config.py:

choose Modbus TCP or RTU

add device IPs/IDs (unit IDs)

set default registers to poll

------Safety Note------

Writing Modbus registers can change device behavior. This UI uses an “ARMED” toggle before writes, but you should still use it only on devices you understand.


---

## File structure

modbus-dashboard/
app.py
config.py
requirements.txt
README.md
templates/
index.html
static/
app.js
style.css

