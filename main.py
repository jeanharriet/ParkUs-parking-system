"""SmartPark KE - a small, self-contained parking management web app."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from flask import Flask, jsonify, render_template_string, request


app = Flask(__name__)
DATABASE = Path(__file__).with_name("smartpark.db")
EAT = timezone(timedelta(hours=3))


def now_eat():
	"""Return the current time in East Africa Time."""
	return datetime.now(EAT)


def parse_time(value):
	return datetime.fromisoformat(value.replace("Z", "+00:00"))


def calculate_fee(entry_time, exit_time):
	"""Apply the specification's exact duration boundaries in minutes."""
	seconds = max(0, (exit_time - entry_time).total_seconds())
	if seconds <= 30 * 60:
		return 0
	if seconds <= 2 * 60 * 60:
		return 50
	if seconds <= 4 * 60 * 60:
		return 100
	if seconds <= 6 * 60 * 60:
		return 300
	return 500


def duration_label(entry_time, exit_time):
	total_seconds = max(0, int((exit_time - entry_time).total_seconds()))
	hours, remainder = divmod(total_seconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	return f"{hours}h {minutes}m {seconds}s"


def connect_db():
	connection = sqlite3.connect(DATABASE)
	connection.row_factory = sqlite3.Row
	connection.execute("PRAGMA foreign_keys = ON")
	return connection


def init_db():
	with connect_db() as db:
		db.executescript(
			"""
			CREATE TABLE IF NOT EXISTS vehicles (
				plate_number TEXT PRIMARY KEY,
				vehicle_type TEXT NOT NULL DEFAULT 'Car'
			);
			CREATE TABLE IF NOT EXISTS parking_slots (
				slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
				slot_number TEXT UNIQUE NOT NULL,
				status TEXT NOT NULL DEFAULT 'free',
				zone TEXT NOT NULL DEFAULT 'A'
			);
			CREATE TABLE IF NOT EXISTS parking_sessions (
				session_id INTEGER PRIMARY KEY AUTOINCREMENT,
				plate_number TEXT NOT NULL REFERENCES vehicles(plate_number),
				slot_id INTEGER NOT NULL REFERENCES parking_slots(slot_id),
				entry_time TEXT NOT NULL,
				exit_time TEXT,
				duration TEXT,
				fee_charged INTEGER NOT NULL DEFAULT 0,
				payment_status TEXT NOT NULL DEFAULT 'unpaid'
			);
			CREATE TABLE IF NOT EXISTS payments (
				payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
				session_id INTEGER NOT NULL REFERENCES parking_sessions(session_id),
				amount INTEGER NOT NULL,
				method TEXT NOT NULL,
				timestamp TEXT NOT NULL,
				status TEXT NOT NULL
			);
			CREATE TABLE IF NOT EXISTS barrier_logs (
				log_id INTEGER PRIMARY KEY AUTOINCREMENT,
				session_id INTEGER REFERENCES parking_sessions(session_id),
				barrier_type TEXT NOT NULL,
				timestamp TEXT NOT NULL,
				action TEXT NOT NULL
			);
			"""
		)
		if db.execute("SELECT COUNT(*) FROM parking_slots").fetchone()[0] == 0:
			db.executemany(
				"INSERT INTO parking_slots (slot_number, zone) VALUES (?, ?)",
				[(f"A-{number:02}", "A") for number in range(1, 21)],
			)


def row_to_dict(row):
	return dict(row) if row else None


@app.get("/")
def index():
	return render_template_string(PAGE)


@app.get("/api/slots")
def get_slots():
	with connect_db() as db:
		slots = [row_to_dict(row) for row in db.execute(
			"SELECT slot_id, slot_number, status, zone FROM parking_slots ORDER BY slot_id"
		)]
	return jsonify(slots=slots, updated_at=now_eat().isoformat())


@app.post("/api/entry")
def create_entry():
	payload = request.get_json(silent=True) or {}
	plate = str(payload.get("plate_number", "")).strip().upper()
	vehicle_type = str(payload.get("vehicle_type", "Car")).strip() or "Car"
	if not plate:
		return jsonify(error="Plate number is required."), 400
	with connect_db() as db:
		active = db.execute(
			"SELECT session_id FROM parking_sessions WHERE plate_number = ? AND exit_time IS NULL",
			(plate,),
		).fetchone()
		if active:
			return jsonify(error="This vehicle already has an active session."), 409
		slot = db.execute(
			"SELECT * FROM parking_slots WHERE status = 'free' ORDER BY slot_id LIMIT 1"
		).fetchone()
		if not slot:
			return jsonify(error="The parking lot is full."), 409
		entry_time = now_eat().isoformat()
		db.execute("INSERT OR IGNORE INTO vehicles VALUES (?, ?)", (plate, vehicle_type))
		cursor = db.execute(
			"INSERT INTO parking_sessions (plate_number, slot_id, entry_time) VALUES (?, ?, ?)",
			(plate, slot["slot_id"], entry_time),
		)
		db.execute("UPDATE parking_slots SET status = 'occupied' WHERE slot_id = ?", (slot["slot_id"],))
		db.execute(
			"INSERT INTO barrier_logs (session_id, barrier_type, timestamp, action) VALUES (?, 'entry', ?, 'opened')",
			(cursor.lastrowid, entry_time),
		)
		return jsonify(
			message="Entry recorded and entry barrier opened.",
			ticket_id=cursor.lastrowid,
			plate_number=plate,
			slot_number=slot["slot_number"],
			entry_time=entry_time,
		), 201


def active_session(plate):
	with connect_db() as db:
		return db.execute(
			"""SELECT s.*, p.slot_number FROM parking_sessions s
			   JOIN parking_slots p ON p.slot_id = s.slot_id
			   WHERE s.plate_number = ? AND s.exit_time IS NULL""",
			(plate.upper(),),
		).fetchone()


@app.get("/api/exit/<plate>")
def quote_exit(plate):
	session = active_session(plate.strip())
	if not session:
		return jsonify(error="No active parking session found for this plate."), 404
	entry = parse_time(session["entry_time"])
	exit_time = now_eat()
	return jsonify(
		session_id=session["session_id"], plate_number=session["plate_number"],
		slot_number=session["slot_number"], entry_time=session["entry_time"],
		duration=duration_label(entry, exit_time), fee=calculate_fee(entry, exit_time),
	)


@app.post("/api/pay")
def process_payment():
	payload = request.get_json(silent=True) or {}
	plate = str(payload.get("plate_number", "")).strip().upper()
	method = str(payload.get("method", "M-Pesa"))
	session = active_session(plate)
	if not session:
		return jsonify(error="No active parking session found for this plate."), 404
	entry = parse_time(session["entry_time"])
	exit_time = now_eat()
	fee = calculate_fee(entry, exit_time)
	duration = duration_label(entry, exit_time)
	with connect_db() as db:
		db.execute(
			"UPDATE parking_sessions SET exit_time = ?, duration = ?, fee_charged = ?, payment_status = 'paid' WHERE session_id = ?",
			(exit_time.isoformat(), duration, fee, session["session_id"]),
		)
		db.execute("UPDATE parking_slots SET status = 'free' WHERE slot_id = ?", (session["slot_id"],))
		db.execute(
			"INSERT INTO payments (session_id, amount, method, timestamp, status) VALUES (?, ?, ?, ?, 'confirmed')",
			(session["session_id"], fee, method, exit_time.isoformat()),
		)
		db.execute(
			"INSERT INTO barrier_logs (session_id, barrier_type, timestamp, action) VALUES (?, 'exit', ?, 'opened')",
			(session["session_id"], exit_time.isoformat()),
		)
	return jsonify(message="Payment confirmed. Exit barrier opened.", duration=duration, fee=fee, barrier="open")


@app.get("/api/reports")
def reports():
	with connect_db() as db:
		current = db.execute(
			"""SELECT s.plate_number, p.slot_number, s.entry_time FROM parking_sessions s
			   JOIN parking_slots p ON p.slot_id = s.slot_id WHERE s.exit_time IS NULL ORDER BY s.entry_time DESC"""
		).fetchall()
		revenue = db.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'confirmed'").fetchone()[0]
		total = db.execute("SELECT COUNT(*) FROM parking_slots").fetchone()[0]
		occupied = db.execute("SELECT COUNT(*) FROM parking_slots WHERE status = 'occupied'").fetchone()[0]
	return jsonify(sessions=[row_to_dict(row) for row in current], revenue=revenue, total_slots=total, occupied=occupied)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartPark KE</title><style>
:root{--ink:#10242a;--muted:#678087;--paper:#f5f8f5;--line:#d7e3df;--teal:#007f7b;--lime:#b9db54;--coral:#e86f51;--white:#fff}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:Georgia,'Times New Roman',serif;background:radial-gradient(circle at 80% 0,#e3f1dd 0,transparent 35%),var(--paper)}
button,input,select{font:inherit}header{max-width:1180px;margin:auto;padding:32px 22px 20px;display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid var(--line)}
.brand{font-size:clamp(2rem,5vw,4rem);line-height:.9;letter-spacing:-2px}.brand span{color:var(--teal)}.eyebrow{font:700 11px Arial,sans-serif;letter-spacing:2px;text-transform:uppercase;color:var(--teal)}.clock{font:14px Arial,sans-serif;color:var(--muted);text-align:right}
main{max-width:1180px;margin:auto;padding:26px 22px 60px}.hero{display:grid;grid-template-columns:1.2fr .8fr;gap:20px;align-items:end;margin-bottom:28px}.hero h1{font-size:clamp(2.2rem,5vw,5.5rem);font-weight:400;line-height:.95;margin:0 0 14px;max-width:700px}.hero p{font:16px Arial,sans-serif;color:var(--muted);max-width:590px}.metric{background:var(--ink);color:white;padding:24px;border-radius:4px}.metric strong{display:block;font-size:4rem;color:var(--lime);line-height:1}.metric small{font:12px Arial,sans-serif;text-transform:uppercase;letter-spacing:1px}
.layout{display:grid;grid-template-columns:1.35fr .65fr;gap:22px}.panel{background:rgba(255,255,255,.82);border:1px solid var(--line);padding:22px;border-radius:4px}.panel h2{font-size:26px;font-weight:400;margin:0 0 5px}.sub{font:13px Arial,sans-serif;color:var(--muted);margin:0 0 20px}.slots{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.slot{aspect-ratio:1.3;border:0;border-radius:3px;padding:7px;text-align:left;color:var(--ink);background:#dcefc4;cursor:default}.slot b{display:block;font:700 13px Arial,sans-serif}.slot small{font:11px Arial,sans-serif}.slot.occupied{background:var(--coral);color:white}.legend{display:flex;gap:14px;font:12px Arial,sans-serif;color:var(--muted);margin-top:15px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;background:#dcefc4}.dot.red{background:var(--coral)}
form{display:grid;gap:10px}label{font:700 11px Arial,sans-serif;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}input,select{width:100%;padding:12px;border:1px solid var(--line);background:white;color:var(--ink);border-radius:2px}button{border:0;background:var(--teal);color:white;padding:13px 16px;cursor:pointer;border-radius:2px;font-weight:bold}button:hover{background:#005d5a}.result{margin-top:14px;padding:13px;background:#edf7e4;font:13px Arial,sans-serif;line-height:1.6}.result.error{background:#fff0ec;color:#9b3520}.quote{font-size:28px;color:var(--teal);font-weight:bold}.admin{margin-top:22px}.stats{display:flex;gap:30px;font:14px Arial,sans-serif;color:var(--muted)}.stats strong{display:block;font-size:24px;color:var(--ink)}table{width:100%;border-collapse:collapse;font:13px Arial,sans-serif;margin-top:17px}th,td{text-align:left;padding:10px 5px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px}@media(max-width:760px){header{align-items:start}.clock{font-size:11px}.hero,.layout{grid-template-columns:1fr}.slots{grid-template-columns:repeat(4,1fr)}.brand{font-size:2.3rem}.panel{padding:17px}}
</style></head><body><header><div><div class="eyebrow">Automated parking / Kenya</div><div class="brand">SmartPark <span>KE</span></div></div><div class="clock" id="clock"></div></header><main>
<section class="hero"><div><div class="eyebrow">Gate status: open</div><h1>Know your space before you enter.</h1><p>Live occupancy, precise parking fees, and a payment-confirmed exit barrier in one calm control surface.</p></div><div class="metric"><small>Spaces available</small><strong id="available">--</strong><span id="occupancy">Loading live status</span></div></section>
<section class="layout"><div class="panel"><h2>Live parking map</h2><p class="sub">Green spaces are available. Red spaces are currently occupied.</p><div class="slots" id="slots"></div><div class="legend"><span><i class="dot"></i>Available</span><span><i class="dot red"></i>Occupied</span></div></div>
<div class="panel"><h2>Vehicle entry</h2><p class="sub">Record an arrival and reserve the next available space.</p><form id="entryForm"><label for="entryPlate">Registration plate</label><input id="entryPlate" placeholder="e.g. KDA 248M" required><label for="vehicleType">Vehicle type</label><select id="vehicleType"><option>Car</option><option>Motorcycle</option><option>SUV</option><option>Van</option></select><button>Assign parking space</button></form><div id="entryResult"></div><hr style="border:0;border-top:1px solid var(--line);margin:25px 0"><h2>Vehicle exit</h2><p class="sub">Get the exact fee, then confirm payment to release the barrier.</p><form id="exitForm"><label for="exitPlate">Registration plate</label><input id="exitPlate" placeholder="e.g. KDA 248M" required><label for="method">Payment method</label><select id="method"><option>M-Pesa</option><option>Cash</option><option>Card</option></select><button>Calculate fee</button></form><div id="exitResult"></div></div></section>
<section class="panel admin"><h2>Operations snapshot</h2><p class="sub">Live sessions and confirmed payment revenue.</p><div class="stats"><div><strong id="activeCount">--</strong>active sessions</div><div><strong id="revenue">Kshs. --</strong>total revenue</div></div><table><thead><tr><th>Plate</th><th>Slot</th><th>Entry time</th></tr></thead><tbody id="sessions"></tbody></table></section></main>
<script>
const $=id=>document.getElementById(id); const money=value=>`Kshs. ${Number(value).toLocaleString()}`;
function message(target,text,error=false){$(target).innerHTML=`<div class="result${error?' error':''}">${text}</div>`}
async function refresh(){const [slotData,report]=await Promise.all([fetch('/api/slots').then(r=>r.json()),fetch('/api/reports').then(r=>r.json())]);const free=slotData.slots.filter(s=>s.status==='free').length;$('available').textContent=free;$('occupancy').textContent=`${slotData.slots.length-free} of ${slotData.slots.length} spaces occupied`;$('slots').innerHTML=slotData.slots.map(s=>`<div class="slot ${s.status}"><b>${s.slot_number}</b><small>${s.status==='free'?'AVAILABLE':'OCCUPIED'}</small></div>`).join('');$('activeCount').textContent=report.occupied;$('revenue').textContent=money(report.revenue);$('sessions').innerHTML=report.sessions.length?report.sessions.map(s=>`<tr><td>${s.plate_number}</td><td>${s.slot_number}</td><td>${new Date(s.entry_time).toLocaleString()}</td></tr>`).join(''):'<tr><td colspan="3">No active sessions</td></tr>'}
$('entryForm').onsubmit=async e=>{e.preventDefault();const r=await fetch('/api/entry',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plate_number:$('entryPlate').value,vehicle_type:$('vehicleType').value})});const d=await r.json();if(!r.ok)return message('entryResult',d.error,true);message('entryResult',`Ticket <b>#${d.ticket_id}</b> issued. Slot <b>${d.slot_number}</b> assigned. Entry barrier opened.`);e.target.reset();refresh()};
$('exitForm').onsubmit=async e=>{e.preventDefault();const plate=$('exitPlate').value;const r=await fetch('/api/exit/'+encodeURIComponent(plate));const d=await r.json();if(!r.ok)return message('exitResult',d.error,true);$('exitResult').innerHTML=`<div class="result">Slot <b>${d.slot_number}</b> · Parked <b>${d.duration}</b><div class="quote">${money(d.fee)}</div><button id="pay" type="button">Confirm payment & open barrier</button></div>`;$('pay').onclick=async()=>{const p=await fetch('/api/pay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plate_number:plate,method:$('method').value})});const x=await p.json();if(!p.ok)return message('exitResult',x.error,true);message('exitResult',`Payment confirmed for <b>${money(x.fee)}</b>. Exit barrier is <b>OPEN</b>.`);e.target.reset();refresh()}};
setInterval(()=>{$('clock').textContent=new Intl.DateTimeFormat('en-KE',{dateStyle:'medium',timeStyle:'medium',timeZone:'Africa/Nairobi'}).format(new Date())},1000);setInterval(refresh,10000);refresh();
</script></body></html>"""


if __name__ == "__main__":
	init_db()
	app.run(debug=True, host="127.0.0.1", port=5000)
