# SmartPark KE

SmartPark KE is a Flask + SQLite parking management system based on the supplied assignment specification. It provides a live slot map, vehicle entry and first-free-slot allocation, exact fee quotes, simulated M-Pesa/cash/card payment, automatic slot release, barrier event logging, and an operations snapshot.

## Run locally

```text
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py main.py
```

Open `http://127.0.0.1:5000`. The database is created automatically as `smartpark.db` and starts with 20 free slots.

## Fee logic

Elapsed time is calculated from the stored EAT entry timestamp to the EAT exit timestamp. The inclusive boundaries are: `<= 30 minutes: Kshs. 0`, `<= 2 hours: Kshs. 50`, `<= 4 hours: Kshs. 100`, `<= 6 hours: Kshs. 300`, and over 6 hours: `Kshs. 500`.

## API

- `GET /api/slots` - live slot statuses
- `POST /api/entry` - accepts `{ "plate_number": "KDA 248M" }`
- `GET /api/exit/<plate>` - returns duration and fee quote
- `POST /api/pay` - confirms payment and opens the exit barrier
- `GET /api/reports` - active sessions, occupancy, and revenue

## Modules and data model

The application maps the specification into slot availability, entry, exit/fee calculation, payment, barrier control, reporting, and persistence modules. SQLite stores `vehicles`, `parking_slots`, `parking_sessions`, `payments`, and `barrier_logs`. Active sessions are indexed by plate through the database, while the ordered slot query provides deterministic first-free-slot allocation. Every entry and paid exit writes a barrier log for auditability.

End-to-end flow: entry creates a session and marks a slot occupied; exit quotes the fee; confirmed payment closes the session, records payment, frees the slot, and writes an `exit/opened` barrier event.