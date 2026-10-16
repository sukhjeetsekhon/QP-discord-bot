import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import config


def get_db_connection() -> sqlite3.Connection:
    """Create and return a database connection with row factory enabled."""
    db_path = config.DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initialize all SQLite tables."""
    conn = get_db_connection()
    with conn:
        # 1. Team Budgets
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_budgets (
                team_number INTEGER PRIMARY KEY,
                total_budget REAL DEFAULT 50.0,
                spent REAL DEFAULT 0.0
            );
        """)

        # 2. Hardware Purchases
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hardware_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_channel_id INTEGER,
                team_number INTEGER,
                requester_id INTEGER,
                item_name TEXT,
                cost REAL,
                status TEXT DEFAULT 'approved',
                approved_by_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Inventory Items
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE COLLATE NOCASE,
                category TEXT DEFAULT 'General',
                total_qty INTEGER DEFAULT 1,
                available_qty INTEGER DEFAULT 1,
                location TEXT DEFAULT 'IEEE Lab'
            );
        """)

        # 4. Inventory Loans (Checkout / Return)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER REFERENCES inventory_items(id),
                team_number INTEGER,
                borrower_id INTEGER,
                quantity INTEGER DEFAULT 1,
                status TEXT DEFAULT 'borrowed',
                borrowed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                returned_at TIMESTAMP
            );
        """)

        # 5. Mentor Help Queue
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mentor_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                team_number INTEGER,
                requester_id INTEGER,
                location TEXT,
                description TEXT,
                status TEXT DEFAULT 'waiting',
                claimed_by_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            );
        """)

        # Initialize default budgets for all teams if missing
        for t in range(1, config.MAX_TEAMS + 1):
            conn.execute("""
                INSERT OR IGNORE INTO team_budgets (team_number, total_budget, spent)
                VALUES (?, ?, 0.0);
            """, (t, config.DEFAULT_TEAM_BUDGET))
    conn.close()


# ==========================================
# BUDGET & HARDWARE PURCHASES FUNCTIONS
# ==========================================

def get_team_budget(team_number: int) -> Dict[str, Any]:
    """Retrieve budget and purchase records for a specific team."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT team_number, total_budget, spent FROM team_budgets WHERE team_number = ?",
        (team_number,)
    ).fetchone()

    if not row:
        total = config.DEFAULT_TEAM_BUDGET
        spent = 0.0
    else:
        total = row["total_budget"]
        spent = row["spent"]

    purchases = conn.execute(
        "SELECT id, ticket_channel_id, item_name, cost, status, approved_by_id, created_at "
        "FROM hardware_purchases WHERE team_number = ? ORDER BY id DESC",
        (team_number,)
    ).fetchall()

    conn.close()
    return {
        "team_number": team_number,
        "total_budget": total,
        "spent": spent,
        "remaining": round(total - spent, 2),
        "purchases": [dict(p) for p in purchases],
    }


def add_hardware_purchase(
    ticket_channel_id: int,
    team_number: int,
    requester_id: int,
    item_name: str,
    cost: float,
    approved_by_id: int,
) -> int:
    """Record an approved hardware purchase and deduct from the team's budget."""
    conn = get_db_connection()
    with conn:
        cursor = conn.execute("""
            INSERT INTO hardware_purchases (
                ticket_channel_id, team_number, requester_id, item_name, cost, status, approved_by_id
            ) VALUES (?, ?, ?, ?, ?, 'approved', ?)
        """, (ticket_channel_id, team_number, requester_id, item_name, cost, approved_by_id))
        purchase_id = cursor.lastrowid

        # Update spent amount in team_budgets
        conn.execute("""
            INSERT INTO team_budgets (team_number, total_budget, spent)
            VALUES (?, ?, ?)
            ON CONFLICT(team_number) DO UPDATE SET spent = spent + excluded.spent
        """, (team_number, config.DEFAULT_TEAM_BUDGET, cost))
    conn.close()
    return purchase_id


def update_purchase_status(ticket_channel_id: int, status: str) -> bool:
    """Update status of a purchase by ticket channel ID (e.g. 'ordered', 'arrived', 'rejected')."""
    conn = get_db_connection()
    with conn:
        cursor = conn.execute(
            "UPDATE hardware_purchases SET status = ? WHERE ticket_channel_id = ?",
            (status, ticket_channel_id)
        )
        updated = cursor.rowcount > 0
    conn.close()
    return updated


def get_all_budgets_summary() -> List[Dict[str, Any]]:
    """Return all team budgets with spent and remaining balances."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT team_number, total_budget, spent, (total_budget - spent) AS remaining
        FROM team_budgets
        ORDER BY team_number ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_team_budget(team_number: int, total_budget: float):
    """Adjust a team's total budget allocation."""
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO team_budgets (team_number, total_budget, spent)
            VALUES (?, ?, 0.0)
            ON CONFLICT(team_number) DO UPDATE SET total_budget = excluded.total_budget
        """, (team_number, total_budget))
    conn.close()


# ==========================================
# INVENTORY & LOANS FUNCTIONS
# ==========================================

def add_or_update_inventory_item(
    name: str,
    category: str,
    quantity: int,
    location: str,
) -> Dict[str, Any]:
    """Add a new item to inventory or increment existing item's quantity."""
    conn = get_db_connection()
    with conn:
        existing = conn.execute(
            "SELECT * FROM inventory_items WHERE name = ?", (name.strip(),)
        ).fetchone()

        if existing:
            new_total = existing["total_qty"] + quantity
            new_avail = existing["available_qty"] + quantity
            loc = location if location else existing["location"]
            cat = category if category else existing["category"]
            conn.execute("""
                UPDATE inventory_items
                SET total_qty = ?, available_qty = ?, location = ?, category = ?
                WHERE id = ?
            """, (new_total, new_avail, loc, cat, existing["id"]))
            item_id = existing["id"]
        else:
            cursor = conn.execute("""
                INSERT INTO inventory_items (name, category, total_qty, available_qty, location)
                VALUES (?, ?, ?, ?, ?)
            """, (name.strip(), category, quantity, quantity, location))
            item_id = cursor.lastrowid

        item = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return dict(item)


def search_inventory(
    search_query: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search inventory items by keyword or category."""
    conn = get_db_connection()
    sql = "SELECT * FROM inventory_items WHERE 1=1"
    params = []

    if search_query:
        sql += " AND name LIKE ?"
        params.append(f"%{search_query.strip()}%")

    if category:
        sql += " AND category LIKE ?"
        params.append(f"%{category.strip()}%")

    sql += " ORDER BY category ASC, name ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_inventory_item(item_id_or_name: str) -> Optional[Dict[str, Any]]:
    """Look up an inventory item by ID or exact name."""
    conn = get_db_connection()
    if item_id_or_name.isdigit():
        row = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (int(item_id_or_name),)).fetchone()
    else:
        row = conn.execute("SELECT * FROM inventory_items WHERE name = ?", (item_id_or_name.strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def checkout_inventory_item(
    item_id_or_name: str,
    team_number: int,
    borrower_id: int,
    quantity: int = 1,
) -> Tuple[bool, str]:
    """Check out an inventory item to a team, decrementing available quantity."""
    if quantity <= 0:
        return False, "Quantity must be greater than 0."

    item = get_inventory_item(item_id_or_name)
    if not item:
        return False, f"Item `{item_id_or_name}` was not found in inventory."

    if item["available_qty"] < quantity:
        return (
            False,
            f"Not enough stock: only **{item['available_qty']}** of **{item['name']}** available (requested {quantity})."
        )

    conn = get_db_connection()
    with conn:
        # Decrement available quantity
        conn.execute(
            "UPDATE inventory_items SET available_qty = available_qty - ? WHERE id = ?",
            (quantity, item["id"])
        )
        # Record loan
        conn.execute("""
            INSERT INTO inventory_loans (item_id, team_number, borrower_id, quantity, status)
            VALUES (?, ?, ?, ?, 'borrowed')
        """, (item["id"], team_number, borrower_id, quantity))
    conn.close()
    return True, f"Successfully checked out **{quantity}x {item['name']}** to **Team {team_number}**."


def return_inventory_item(
    item_id_or_name: str,
    team_number: int,
    quantity: int = 1,
) -> Tuple[bool, str]:
    """Return a checked-out item from a team, incrementing available quantity."""
    if quantity <= 0:
        return False, "Quantity must be greater than 0."

    item = get_inventory_item(item_id_or_name)
    if not item:
        return False, f"Item `{item_id_or_name}` was not found in inventory."

    conn = get_db_connection()
    with conn:
        # Check active loans for this team and item
        loans = conn.execute("""
            SELECT id, quantity FROM inventory_loans
            WHERE item_id = ? AND team_number = ? AND status = 'borrowed'
            ORDER BY id ASC
        """, (item["id"], team_number)).fetchall()

        if not loans:
            conn.close()
            return False, f"Team {team_number} has no active loans for **{item['name']}**."

        total_borrowed = sum(l["quantity"] for l in loans)
        if quantity > total_borrowed:
            conn.close()
            return False, f"Team {team_number} only has **{total_borrowed}** checked out, but you specified {quantity} to return."

        # Mark loan(s) as returned
        remaining_to_return = quantity
        now_str = datetime.now().isoformat()
        for loan in loans:
            loan_id = loan["id"]
            loan_qty = loan["quantity"]
            if remaining_to_return >= loan_qty:
                conn.execute(
                    "UPDATE inventory_loans SET status = 'returned', returned_at = ? WHERE id = ?",
                    (now_str, loan_id)
                )
                remaining_to_return -= loan_qty
            else:
                # Partial return: split the loan row
                conn.execute(
                    "UPDATE inventory_loans SET quantity = quantity - ? WHERE id = ?",
                    (remaining_to_return, loan_id)
                )
                conn.execute("""
                    INSERT INTO inventory_loans (item_id, team_number, borrower_id, quantity, status, returned_at)
                    VALUES (?, ?, ?, ?, 'returned', ?)
                """, (item["id"], team_number, 0, remaining_to_return, now_str))
                remaining_to_return = 0
                break

        # Increment available quantity in inventory
        conn.execute(
            "UPDATE inventory_items SET available_qty = available_qty + ? WHERE id = ?",
            (quantity, item["id"])
        )

    conn.close()
    return True, f"Successfully returned **{quantity}x {item['name']}** from **Team {team_number}**."


def get_borrowed_items(team_number: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve all active inventory loans, optionally filtered by team."""
    conn = get_db_connection()
    sql = """
        SELECT l.id AS loan_id, l.team_number, l.borrower_id, l.quantity, l.borrowed_at,
               i.id AS item_id, i.name AS item_name, i.category, i.location
        FROM inventory_loans l
        JOIN inventory_items i ON l.item_id = i.id
        WHERE l.status = 'borrowed'
    """
    params = []
    if team_number is not None:
        sql += " AND l.team_number = ?"
        params.append(team_number)

    sql += " ORDER BY l.team_number ASC, l.borrowed_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==========================================
# MENTOR HELP QUEUE FUNCTIONS
# ==========================================

def create_mentor_request(
    team_number: int,
    requester_id: int,
    location: str,
    description: str,
) -> int:
    """Create a new mentor help ticket."""
    conn = get_db_connection()
    with conn:
        cursor = conn.execute("""
            INSERT INTO mentor_requests (team_number, requester_id, location, description, status)
            VALUES (?, ?, ?, ?, 'waiting')
        """, (team_number, requester_id, location.strip(), description.strip()))
        req_id = cursor.lastrowid
    conn.close()
    return req_id


def set_mentor_request_message_id(request_id: int, message_id: int):
    """Store the Discord message ID for the mentor queue card."""
    conn = get_db_connection()
    with conn:
        conn.execute("UPDATE mentor_requests SET message_id = ? WHERE id = ?", (message_id, request_id))
    conn.close()


def claim_mentor_request(request_id: int, mentor_id: int) -> bool:
    """Mark a mentor ticket as claimed by an officer/mentor."""
    conn = get_db_connection()
    with conn:
        cursor = conn.execute("""
            UPDATE mentor_requests
            SET status = 'claimed', claimed_by_id = ?
            WHERE id = ? AND status = 'waiting'
        """, (mentor_id, request_id))
        updated = cursor.rowcount > 0
    conn.close()
    return updated


def resolve_mentor_request(request_id: int) -> bool:
    """Mark a mentor ticket as resolved."""
    conn = get_db_connection()
    now_str = datetime.now().isoformat()
    with conn:
        cursor = conn.execute("""
            UPDATE mentor_requests
            SET status = 'resolved', resolved_at = ?
            WHERE id = ? AND status IN ('waiting', 'claimed')
        """, (now_str, request_id))
        updated = cursor.rowcount > 0
    conn.close()
    return updated


def cancel_mentor_request(request_id: int) -> bool:
    """Cancel a mentor ticket."""
    conn = get_db_connection()
    with conn:
        cursor = conn.execute("""
            UPDATE mentor_requests
            SET status = 'cancelled'
            WHERE id = ? AND status = 'waiting'
        """, (request_id,))
        updated = cursor.rowcount > 0
    conn.close()
    return updated


def get_mentor_request(request_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve details for a single mentor request."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM mentor_requests WHERE id = ?", (request_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
