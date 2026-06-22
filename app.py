from flask import Flask, request, jsonify, render_template_string
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "restaurant.db")

# ── Database ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                category    TEXT    NOT NULL,
                price       REAL    NOT NULL,
                description TEXT,
                available   INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS tables (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                number   INTEGER UNIQUE NOT NULL,
                capacity INTEGER DEFAULT 4,
                status   TEXT DEFAULT 'available'   -- available | occupied | reserved
            );

            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                table_id     INTEGER REFERENCES tables(id),
                customer_name TEXT,
                status       TEXT DEFAULT 'pending', -- pending | preparing | served | paid
                total        REAL DEFAULT 0,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id  INTEGER REFERENCES orders(id),
                item_id   INTEGER REFERENCES menu_items(id),
                quantity  INTEGER DEFAULT 1,
                subtotal  REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS reservations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                table_id     INTEGER REFERENCES tables(id),
                customer_name TEXT NOT NULL,
                phone        TEXT,
                party_size   INTEGER NOT NULL,
                reserved_at  TEXT NOT NULL,
                status       TEXT DEFAULT 'confirmed'   -- confirmed | cancelled | completed
            );

            CREATE TABLE IF NOT EXISTS inventory (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT UNIQUE NOT NULL,
                quantity REAL NOT NULL,
                unit     TEXT DEFAULT 'units',
                min_qty  REAL DEFAULT 10
            );
        """)
        conn.commit()
    _seed()

def _seed():
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 0:
            conn.executemany("INSERT INTO menu_items (name,category,price,description) VALUES (?,?,?,?)", [
                ("Paneer Tikka",   "Starter",  180, "Grilled cottage cheese with spices"),
                ("Veg Spring Roll","Starter",  120, "Crispy rolls with vegetable filling"),
                ("Butter Chicken", "Main",     320, "Creamy tomato-based chicken curry"),
                ("Dal Makhani",    "Main",     220, "Slow-cooked black lentils"),
                ("Chicken Biryani","Main",     350, "Fragrant basmati rice with chicken"),
                ("Garlic Naan",    "Bread",     50, "Tandoor-baked bread with garlic"),
                ("Gulab Jamun",    "Dessert",   80, "Soft milk-solid balls in syrup"),
                ("Cold Coffee",    "Beverage",  90, "Blended iced coffee"),
            ])
        if conn.execute("SELECT COUNT(*) FROM tables").fetchone()[0] == 0:
            conn.executemany("INSERT INTO tables (number, capacity) VALUES (?,?)", [
                (1,2),(2,2),(3,4),(4,4),(5,4),(6,6),(7,8),(8,8)
            ])
        if conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
            conn.executemany("INSERT INTO inventory (name,quantity,unit,min_qty) VALUES (?,?,?,?)", [
                ("Chicken",  15, "kg", 5),
                ("Paneer",   8,  "kg", 3),
                ("Rice",     25, "kg", 10),
                ("Oil",      10, "L",  3),
                ("Tomatoes", 12, "kg", 4),
            ])
        conn.commit()


init_db()

# ── Frontend ──────────────────────────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CodeAlpha Restaurant Manager</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:'Segoe UI',sans-serif;background:#fff8f0;color:#333;}
    header{background:linear-gradient(135deg,#c2410c,#ea580c);color:white;padding:20px 40px;display:flex;align-items:center;gap:14px;}
    header h1{font-size:22px;} header p{font-size:13px;opacity:.85;}
    nav{background:#1c1917;display:flex;gap:2px;padding:0 20px;}
    nav button{background:none;border:none;color:#d6d3d1;padding:14px 20px;cursor:pointer;font-size:14px;font-weight:600;}
    nav button.active,nav button:hover{color:white;border-bottom:3px solid #ea580c;}
    .container{max-width:1100px;margin:28px auto;padding:0 20px;}
    .panel{display:none;} .panel.active{display:block;}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px;}
    .card{background:white;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.08);padding:20px;}
    .card h3{color:#c2410c;margin-bottom:8px;}
    .badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;margin-bottom:10px;}
    .badge-starter{background:#fef3c7;color:#92400e;}
    .badge-main{background:#fee2e2;color:#991b1b;}
    .badge-bread{background:#fce7f3;color:#9d174d;}
    .badge-dessert{background:#ede9fe;color:#5b21b6;}
    .badge-beverage{background:#dbeafe;color:#1e40af;}
    .badge-available{background:#dcfce7;color:#166534;}
    .badge-occupied{background:#fee2e2;color:#991b1b;}
    .badge-reserved{background:#fef3c7;color:#92400e;}
    .price{font-size:18px;font-weight:700;color:#ea580c;}
    .btn{padding:9px 18px;border:none;border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;}
    .btn-primary{background:#ea580c;color:white;} .btn-primary:hover{background:#c2410c;}
    .btn-green{background:#16a34a;color:white;}   .btn-green:hover{background:#15803d;}
    .btn-red{background:#dc2626;color:white;}     .btn-red:hover{background:#b91c1c;}
    .btn-outline{background:white;border:2px solid #ea580c;color:#ea580c;}
    .form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
    .form-group{margin-bottom:14px;}
    label{display:block;font-size:13px;font-weight:600;margin-bottom:4px;color:#374151;}
    input,select,textarea{width:100%;padding:9px 13px;border:2px solid #e5e7eb;border-radius:7px;font-size:14px;outline:none;}
    input:focus,select:focus{border-color:#ea580c;}
    .msg{padding:11px 15px;border-radius:8px;margin-bottom:14px;font-size:14px;display:none;}
    .msg.ok{background:#dcfce7;color:#166534;display:block;}
    .msg.err{background:#fee2e2;color:#dc2626;display:block;}
    table{width:100%;border-collapse:collapse;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.08);}
    th{background:#c2410c;color:white;padding:12px 16px;text-align:left;font-size:13px;}
    td{padding:10px 16px;border-bottom:1px solid #f5f5f4;font-size:13px;}
    tr:hover td{background:#fff8f0;}
    .alert{background:#fef3c7;border-left:4px solid #f59e0b;padding:10px 14px;border-radius:6px;font-size:13px;margin-bottom:8px;}
    .section-title{font-size:18px;font-weight:700;color:#1c1917;margin-bottom:16px;}
  </style>
</head>
<body>
<header>
  <div>
    <h1>🍽 Restaurant Management System</h1>
    <p>Orders · Tables · Reservations · Inventory</p>
  </div>
</header>
<nav>
  <button class="active" onclick="showTab('menu',this)">🍴 Menu</button>
  <button onclick="showTab('tables',this)">🪑 Tables</button>
  <button onclick="showTab('orders',this)">📋 Orders</button>
  <button onclick="showTab('reservations',this)">📅 Reservations</button>
  <button onclick="showTab('inventory',this)">📦 Inventory</button>
</nav>
<div class="container">

  <!-- MENU -->
  <div class="panel active" id="tab-menu">
    <p class="section-title">Menu Items</p>
    <div class="grid" id="menuGrid">Loading...</div>
  </div>

  <!-- TABLES -->
  <div class="panel" id="tab-tables">
    <p class="section-title">Table Status</p>
    <div class="grid" id="tableGrid">Loading...</div>
  </div>

  <!-- ORDERS -->
  <div class="panel" id="tab-orders">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
      <div class="card">
        <h3 style="margin-bottom:16px">Place New Order</h3>
        <div class="msg" id="orderMsg"></div>
        <div class="form-group"><label>Customer Name</label><input id="oName" placeholder="Customer name"/></div>
        <div class="form-group"><label>Table</label><select id="oTable"><option value="">No table (takeaway)</option></select></div>
        <div class="form-group"><label>Select Items</label>
          <div id="menuCheckboxes" style="max-height:240px;overflow-y:auto;border:2px solid #e5e7eb;border-radius:7px;padding:10px"></div>
        </div>
        <button class="btn btn-primary" onclick="placeOrder()">Place Order</button>
      </div>
      <div>
        <p class="section-title">Active Orders</p>
        <div id="activeOrders">Loading...</div>
      </div>
    </div>
    <div style="margin-top:24px">
      <p class="section-title">All Orders</p>
      <div id="allOrders"></div>
    </div>
  </div>

  <!-- RESERVATIONS -->
  <div class="panel" id="tab-reservations">
    <div style="display:grid;grid-template-columns:1fr 1.5fr;gap:24px">
      <div class="card">
        <h3 style="margin-bottom:16px">New Reservation</h3>
        <div class="msg" id="resMsg"></div>
        <div class="form-group"><label>Name</label><input id="rName" placeholder="Guest name"/></div>
        <div class="form-group"><label>Phone</label><input id="rPhone" placeholder="+91..."/></div>
        <div class="form-group"><label>Party Size</label><input id="rSize" type="number" value="2" min="1"/></div>
        <div class="form-group"><label>Date & Time</label><input id="rDate" type="datetime-local"/></div>
        <div class="form-group"><label>Table</label><select id="rTable"><option value="">Auto-assign</option></select></div>
        <button class="btn btn-primary" onclick="addReservation()">Reserve Table</button>
      </div>
      <div>
        <p class="section-title">Upcoming Reservations</p>
        <div id="resList"></div>
      </div>
    </div>
  </div>

  <!-- INVENTORY -->
  <div class="panel" id="tab-inventory">
    <p class="section-title">Inventory</p>
    <div id="stockAlerts" style="margin-bottom:16px"></div>
    <div id="inventoryTable"></div>
  </div>
</div>

<script>
function showTab(name,btn){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
  if(name==='menu')loadMenu();
  if(name==='tables')loadTables();
  if(name==='orders')loadOrders();
  if(name==='reservations')loadReservations();
  if(name==='inventory')loadInventory();
}

/* ── MENU ── */
async function loadMenu(){
  const r=await fetch('/api/menu');const items=await r.json();
  document.getElementById('menuGrid').innerHTML=items.map(i=>`
    <div class="card">
      <span class="badge badge-${i.category.toLowerCase()}">${i.category}</span>
      <h3>${i.name}</h3>
      <p style="font-size:13px;color:#666;margin:6px 0 12px">${i.description||''}</p>
      <div class="price">₹${i.price}</div>
    </div>`).join('');
  // also populate order checkboxes
  document.getElementById('menuCheckboxes').innerHTML=items.map(i=>`
    <label style="display:flex;align-items:center;gap:8px;padding:5px 0;cursor:pointer">
      <input type="checkbox" value="${i.id}" data-price="${i.price}" data-name="${i.name}">
      ${i.name} — ₹${i.price}
      <input type="number" min="1" value="1" style="width:55px;padding:3px 6px;margin-left:auto" id="qty-${i.id}">
    </label>`).join('');
  // populate table dropdowns
  const tr=await fetch('/api/tables');const tables=await tr.json();
  const oSel=document.getElementById('oTable');
  tables.filter(t=>t.status==='available').forEach(t=>{
    oSel.innerHTML+=`<option value="${t.id}">Table ${t.number} (${t.capacity} seats)</option>`;
  });
  const rSel=document.getElementById('rTable');
  tables.filter(t=>t.status!=='occupied').forEach(t=>{
    rSel.innerHTML+=`<option value="${t.id}">Table ${t.number}</option>`;
  });
}

/* ── TABLES ── */
async function loadTables(){
  const r=await fetch('/api/tables');const tables=await r.json();
  document.getElementById('tableGrid').innerHTML=tables.map(t=>`
    <div class="card" style="text-align:center">
      <span class="badge badge-${t.status}">${t.status.toUpperCase()}</span>
      <h3 style="font-size:28px;margin:8px 0">T${t.number}</h3>
      <p style="color:#666;font-size:13px">Capacity: ${t.capacity} guests</p>
      ${t.status!=='occupied'?`<button class="btn btn-green" style="margin-top:12px" onclick="setTableStatus(${t.id},'occupied')">Mark Occupied</button>`:
        `<button class="btn btn-outline" style="margin-top:12px" onclick="setTableStatus(${t.id},'available')">Mark Available</button>`}
    </div>`).join('');
}

async function setTableStatus(id,status){
  await fetch(`/api/tables/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});
  loadTables();
}

/* ── ORDERS ── */
async function placeOrder(){
  const msg=document.getElementById('orderMsg');msg.className='msg';
  const items=[];
  document.querySelectorAll('#menuCheckboxes input[type=checkbox]:checked').forEach(cb=>{
    items.push({item_id:parseInt(cb.value),quantity:parseInt(document.getElementById('qty-'+cb.value).value)||1});
  });
  if(!items.length){msg.className='msg err';msg.textContent='Select at least one item.';return;}
  const body={customer_name:document.getElementById('oName').value.trim()||'Guest',
               table_id:document.getElementById('oTable').value||null,items};
  const r=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(r.ok){msg.className='msg ok';msg.textContent=`✅ Order #${d.order_id} placed! Total ₹${d.total}`;}
  else{msg.className='msg err';msg.textContent='❌ '+(d.error||'Error');}
  loadOrders();
}

async function loadOrders(){
  const r=await fetch('/api/orders');const orders=await r.json();
  const active=orders.filter(o=>!['paid'].includes(o.status));
  document.getElementById('activeOrders').innerHTML=active.length?active.map(o=>`
    <div class="card" style="margin-bottom:12px">
      <b>Order #${o.id}</b> — ${o.customer_name}<br>
      <span class="badge badge-starter">${o.status}</span> ₹${o.total}<br>
      <small style="color:#888">${o.created_at}</small><br>
      <div style="margin-top:8px;display:flex;gap:8px">
        ${o.status==='pending'?`<button class="btn btn-green" onclick="updateOrder(${o.id},'preparing')">→ Preparing</button>`:''}
        ${o.status==='preparing'?`<button class="btn btn-green" onclick="updateOrder(${o.id},'served')">→ Served</button>`:''}
        ${o.status==='served'?`<button class="btn btn-primary" onclick="updateOrder(${o.id},'paid')">✓ Paid</button>`:''}
      </div>
    </div>`):'<p style="color:#888">No active orders</p>';

  document.getElementById('allOrders').innerHTML=`<table><thead><tr><th>#</th><th>Customer</th><th>Table</th><th>Status</th><th>Total</th><th>Time</th></tr></thead><tbody>`+
    orders.map(o=>`<tr><td>${o.id}</td><td>${o.customer_name}</td><td>${o.table_number||'Takeaway'}</td>
    <td>${o.status}</td><td>₹${o.total}</td><td>${o.created_at}</td></tr>`).join('')+'</tbody></table>';
}

async function updateOrder(id,status){
  await fetch(`/api/orders/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});
  loadOrders();
}

/* ── RESERVATIONS ── */
async function addReservation(){
  const msg=document.getElementById('resMsg');msg.className='msg';
  const body={customer_name:document.getElementById('rName').value.trim(),
    phone:document.getElementById('rPhone').value.trim(),
    party_size:parseInt(document.getElementById('rSize').value),
    reserved_at:document.getElementById('rDate').value,
    table_id:document.getElementById('rTable').value||null};
  if(!body.customer_name||!body.reserved_at){msg.className='msg err';msg.textContent='Name & time required';return;}
  const r=await fetch('/api/reservations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(r.ok){msg.className='msg ok';msg.textContent='✅ Reserved! Table '+d.table_number;}
  else{msg.className='msg err';msg.textContent='❌ '+(d.error||'Error');}
  loadReservations();
}

async function loadReservations(){
  const r=await fetch('/api/reservations');const data=await r.json();
  document.getElementById('resList').innerHTML=data.length?`<table>
    <thead><tr><th>Guest</th><th>Table</th><th>Party</th><th>Time</th><th>Status</th><th>Action</th></tr></thead>
    <tbody>`+data.map(r=>`<tr><td>${r.customer_name}</td><td>T${r.table_number||'?'}</td>
    <td>${r.party_size}</td><td>${r.reserved_at}</td><td>${r.status}</td>
    <td>${r.status==='confirmed'?`<button class="btn btn-red" onclick="cancelRes(${r.id})">Cancel</button>`:'-'}</td></tr>`).join('')+
    '</tbody></table>':'<p style="color:#888">No upcoming reservations</p>';
}

async function cancelRes(id){
  await fetch(`/api/reservations/${id}`,{method:'DELETE'});
  loadReservations();
}

/* ── INVENTORY ── */
async function loadInventory(){
  const r=await fetch('/api/inventory');const data=await r.json();
  const low=data.filter(i=>i.quantity<=i.min_qty);
  document.getElementById('stockAlerts').innerHTML=low.map(i=>
    `<div class="alert">⚠️ <b>${i.name}</b> is running low — only ${i.quantity} ${i.unit} left (min: ${i.min_qty})</div>`).join('');
  document.getElementById('inventoryTable').innerHTML=`<table>
    <thead><tr><th>Item</th><th>Quantity</th><th>Unit</th><th>Min Level</th><th>Status</th><th>Update</th></tr></thead>
    <tbody>`+data.map(i=>`<tr>
      <td><b>${i.name}</b></td>
      <td>${i.quantity}</td><td>${i.unit}</td><td>${i.min_qty}</td>
      <td>${i.quantity<=i.min_qty?'<span style="color:#dc2626;font-weight:700">LOW</span>':'<span style="color:#16a34a;font-weight:700">OK</span>'}</td>
      <td><input type="number" id="inv-${i.id}" value="${i.quantity}" style="width:80px">
          <button class="btn btn-green" style="margin-left:6px" onclick="updateInv(${i.id})">Save</button>
      </td></tr>`).join('')+'</tbody></table>';
}

async function updateInv(id){
  const qty=parseFloat(document.getElementById('inv-'+id).value);
  await fetch(`/api/inventory/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({quantity:qty})});
  loadInventory();
}

// initial load
loadMenu();
</script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

# Menu
@app.route("/api/menu", methods=["GET"])
def get_menu():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM menu_items WHERE available=1 ORDER BY category,name").fetchall()
    return jsonify([dict(r) for r in rows])

# Tables
@app.route("/api/tables", methods=["GET"])
def get_tables():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tables ORDER BY number").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/tables/<int:table_id>", methods=["PATCH"])
def update_table(table_id):
    data = request.get_json() or {}
    status = data.get("status")
    if status not in ("available", "occupied", "reserved"):
        return jsonify({"error": "Invalid status"}), 400
    with get_db() as conn:
        conn.execute("UPDATE tables SET status=? WHERE id=?", (status, table_id))
        conn.commit()
    return jsonify({"message": "Updated"})

# Orders
@app.route("/api/orders", methods=["GET"])
def get_orders():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT o.*, t.number AS table_number
            FROM orders o LEFT JOIN tables t ON t.id = o.table_id
            ORDER BY o.created_at DESC LIMIT 50
        """).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/orders", methods=["POST"])
def place_order():
    d = request.get_json() or {}
    items = d.get("items", [])
    if not items:
        return jsonify({"error": "items are required"}), 400
    total = 0.0
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO orders (table_id, customer_name, total) VALUES (?,?,0)",
            (d.get("table_id"), d.get("customer_name", "Guest"))
        )
        order_id = cur.lastrowid
        for it in items:
            row = conn.execute("SELECT price FROM menu_items WHERE id=?", (it["item_id"],)).fetchone()
            if not row:
                continue
            subtotal = row["price"] * it.get("quantity", 1)
            total += subtotal
            conn.execute("INSERT INTO order_items (order_id,item_id,quantity,subtotal) VALUES (?,?,?,?)",
                         (order_id, it["item_id"], it.get("quantity", 1), subtotal))
        conn.execute("UPDATE orders SET total=? WHERE id=?", (total, order_id))
        if d.get("table_id"):
            conn.execute("UPDATE tables SET status='occupied' WHERE id=?", (d["table_id"],))
        conn.commit()
    return jsonify({"message": "Order placed", "order_id": order_id, "total": total}), 201

@app.route("/api/orders/<int:order_id>", methods=["PATCH"])
def update_order(order_id):
    data = request.get_json() or {}
    status = data.get("status")
    if status not in ("pending", "preparing", "served", "paid"):
        return jsonify({"error": "Invalid status"}), 400
    with get_db() as conn:
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        if status == "paid":
            row = conn.execute("SELECT table_id FROM orders WHERE id=?", (order_id,)).fetchone()
            if row and row["table_id"]:
                conn.execute("UPDATE tables SET status='available' WHERE id=?", (row["table_id"],))
        conn.commit()
    return jsonify({"message": "Order updated"})

# Reservations
@app.route("/api/reservations", methods=["GET"])
def get_reservations():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT r.*, t.number AS table_number
            FROM reservations r LEFT JOIN tables t ON t.id = r.table_id
            WHERE r.status = 'confirmed' ORDER BY r.reserved_at
        """).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/reservations", methods=["POST"])
def add_reservation():
    d = request.get_json() or {}
    if not d.get("customer_name") or not d.get("reserved_at") or not d.get("party_size"):
        return jsonify({"error": "customer_name, party_size, reserved_at required"}), 400

    table_id = d.get("table_id")
    with get_db() as conn:
        if not table_id:
            # Auto-assign smallest available table that fits
            row = conn.execute(
                "SELECT id FROM tables WHERE status != 'occupied' AND capacity >= ? ORDER BY capacity LIMIT 1",
                (d["party_size"],)
            ).fetchone()
            if not row:
                return jsonify({"error": "No available table for that party size"}), 400
            table_id = row["id"]
        conn.execute(
            "INSERT INTO reservations (table_id,customer_name,phone,party_size,reserved_at) VALUES (?,?,?,?,?)",
            (table_id, d["customer_name"], d.get("phone",""), d["party_size"], d["reserved_at"])
        )
        conn.execute("UPDATE tables SET status='reserved' WHERE id=?", (table_id,))
        t = conn.execute("SELECT number FROM tables WHERE id=?", (table_id,)).fetchone()
        conn.commit()
    return jsonify({"message": "Reservation confirmed", "table_number": t["number"]}), 201

@app.route("/api/reservations/<int:res_id>", methods=["DELETE"])
def cancel_reservation(res_id):
    with get_db() as conn:
        row = conn.execute("SELECT table_id FROM reservations WHERE id=?", (res_id,)).fetchone()
        if row and row["table_id"]:
            conn.execute("UPDATE tables SET status='available' WHERE id=?", (row["table_id"],))
        conn.execute("UPDATE reservations SET status='cancelled' WHERE id=?", (res_id,))
        conn.commit()
    return jsonify({"message": "Reservation cancelled"})

# Inventory
@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM inventory ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/inventory/<int:item_id>", methods=["PATCH"])
def update_inventory(item_id):
    d = request.get_json() or {}
    qty = d.get("quantity")
    if qty is None or qty < 0:
        return jsonify({"error": "quantity must be >= 0"}), 400
    with get_db() as conn:
        conn.execute("UPDATE inventory SET quantity=? WHERE id=?", (qty, item_id))
        conn.commit()
    return jsonify({"message": "Inventory updated"})

if __name__ == "__main__":
    app.run(debug=True, port=5003)
