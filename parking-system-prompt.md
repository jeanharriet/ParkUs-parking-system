# Build Prompt: "SmartPark KE" — Modern Automated Parking Management System

Use this prompt (with an AI coding assistant, or as your own build spec) to design and implement the full system for the Systems Analysis and Design assignment.

---

## 1. Project Framing

Build a **web-based, modern parking management system** called **"SmartPark KE"** for a client automating parking operations in Kenya. The system must:

1. Show drivers a **real-time visual display** of available parking slots before they enter.
2. **Record vehicles on arrival** (entry event, timestamp, slot assignment).
3. On exit, **automatically calculate** total time parked and the fee owed.
4. **Open the exit barrier automatically** once payment is confirmed.

Deliver this as a working **web application** (browser-based UI + backend + database), built in **Python** (preferred: Flask or Django + SQLite/PostgreSQL) — note if C++/Java is chosen instead, adapt architecture accordingly. Code must be **well-commented** throughout.

---

## 2. Fee Structure (hard-code exactly as given)

| Duration Parked | Fee (Kshs.) |
|---|---|
| Up to 30 minutes | Free (0) |
| Up to 2 hours | 50 |
| Up to 4 hours | 100 |
| Up to 6 hours | 300 |
| Over 6 hours | 500 |

Fee calculation must use **exact elapsed time** (entry timestamp → exit timestamp) and apply the correct tier, including edge cases (e.g., exactly 30:00, exactly 2:00:00).

---

## 3. Required Deliverables (map to assignment parts)

### A. Critical analysis of Terms of Reference → Module breakdown
Propose and justify these modules (expand/rename as needed, but justify each against the ToR):
1. **Slot Availability & Display Module** — tracks real-time occupancy, renders visual map/grid of free vs occupied slots to a public-facing screen/webpage.
2. **Vehicle Entry (Check-In) Module** — captures vehicle detail (plate number, entry timestamp), assigns/reserves a slot, issues a ticket/ID (QR code or ticket number), updates slot status.
3. **Vehicle Exit (Check-Out) Module** — looks up the vehicle's entry record, computes elapsed duration, calculates fee via the tiered rule.
4. **Payment Processing Module** — accepts payment (simulate M-Pesa/cash/card), confirms payment, triggers barrier release only on success.
5. **Barrier Control Module** — simulated/actual hardware interface; opens on entry (if slot available) and on exit (if payment confirmed); logs barrier events.
6. **Admin/Reporting Module** — dashboard for management: occupancy history, revenue reports, average duration, peak hours.
7. **Database/Persistence Module** — stores all entities and transaction history (see §5).

For each module: describe its **purpose**, **inputs/outputs**, and **interaction with other modules** (a simple module interaction diagram description is acceptable).

### B. Algorithm for each module
Provide pseudocode (not full code) for:
- Slot availability lookup & display refresh
- Vehicle entry / slot allocation (e.g., nearest-free-slot or first-free-slot strategy)
- Duration calculation (timestamp difference → hours/minutes)
- Fee calculation (tiered decision logic — as an explicit decision table/flowchart, not just if/else prose)
- Payment verification and barrier trigger
- Full end-to-end flow: **Entry → Parked → Exit request → Fee calc → Payment → Barrier open**

### C. Data structures — with justification
Propose structures such as:
- **Hash map / dictionary** keyed by plate number or ticket ID → active parking record (O(1) lookup on exit).
- **Array/list or bitset** representing the slot grid (O(1) status flips, easy to render visually).
- **Queue** for entry requests when the lot is full (FIFO fairness).
- **Priority queue / min-heap** (optional) for nearest-available-slot allocation.
- **Stack or log/list** for barrier event history / audit trail.
For each: explain **why** it fits the access pattern (frequency of lookups vs. inserts vs. updates), and its complexity.

### D. Dynamic database design
Design a normalized relational schema (ERD description + DDL), minimally:
- `Vehicles` (plate_number PK, vehicle_type, owner_info optional)
- `ParkingSlots` (slot_id PK, slot_number, status: free/occupied/reserved, zone/floor)
- `ParkingSessions` (session_id PK, plate_number FK, slot_id FK, entry_time, exit_time, duration, fee_charged, payment_status)
- `Payments` (payment_id PK, session_id FK, amount, method, timestamp, status)
- `BarrierLogs` (log_id PK, session_id FK, barrier_type: entry/exit, timestamp, action)

Explain why it's "dynamic": slot status updates in real time, sessions are created/closed continuously, and the schema supports historical reporting without losing live-state performance. Include at least one ER diagram (can be described in Mermaid syntax).

---

## 4. Use Cases to derive first
Before modules, list actor-based use cases, e.g.:
- Driver views available slots (public display)
- Driver's vehicle enters → system logs entry, assigns slot
- Driver's vehicle exits → system computes fee, requests payment
- Driver pays → barrier opens
- Admin views daily revenue/occupancy report
- System flags lot-full state and denies/queues entry

---

## 5. Functional Web System Requirements
- **Frontend**: A public "Available Slots" page/dashboard (auto-refreshing or WebSocket-driven grid/map view, green = free, red = occupied).
- **Entry simulation page**: form/button to simulate a car arriving (input plate number) → assigns slot, shows ticket.
- **Exit simulation page**: input plate number/ticket → system shows duration + fee → "Pay" button → on success, shows "Barrier Open" animation/message.
- **Admin dashboard**: table of current sessions, total revenue today, occupancy %.
- **Backend API** (REST endpoints) for: get slots, create entry, get fee quote, process payment, get reports.
- **Persistence**: database (SQLite for demo, PostgreSQL-ready) backing all modules.
- **Well-commented code**: docstrings/comments explaining each function, especially the fee-tier logic and slot-allocation logic.

---

## 6. Non-functional / presentation requirements
- Clean, simple, mobile-friendly UI (drivers will view it on a screen at the gate).
- Currency displayed as "Kshs." consistently.
- Timestamps in East Africa Time (EAT, UTC+3).
- Include a README (for the GitHub submission) covering: setup instructions, architecture overview, module list, and how fee tiers are implemented.
- Individual GitHub repo with meaningful commit history (not one giant commit) since submission is individual via GitHub.

---

## 7. Suggested build order (for an AI assistant or self-paced build)
1. Design ERD + create database schema and seed data (e.g., 20 slots).
2. Build backend fee-calculation function + unit tests covering every tier boundary.
3. Build slot allocation + entry/exit API endpoints.
4. Build the public slot-display frontend.
5. Build entry/exit simulation UI + payment simulation.
6. Build admin dashboard/reports.
7. Write README + comments + push to GitHub with logical commits.

---

**Instruction to the assistant using this prompt:** Work through sections A–D as design documentation first (module list, algorithms as pseudocode, data structures with justification, ERD/schema), then implement the functional web system per §5–7, keeping code thoroughly commented and the fee logic exactly matching §2.
