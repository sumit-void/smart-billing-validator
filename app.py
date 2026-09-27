"""
app.py — Smart Billing Validator (Flask Backend)

All Python logic in one file:
  - Database (SQLite, CRUD, Aggregation)
  - Models (Product, BillItem, Bill — OOP, Properties, Magic Methods)
  - Validators (ABC, Inheritance, Polymorphism)
  - Analytics Engine
  - Flask API Routes
  - Sample Data Seeder

Run: python app.py
Open: http://localhost:5000
"""

import sqlite3
import os
import random
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from flask import Flask, render_template, request, jsonify

# ─── App Setup ───────────────────────────────────────────────────────────────

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "billing_validator.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BillingValidator")


# ═════════════════════════════════════════════════════════════════════════════
#  ENUMS
# ═════════════════════════════════════════════════════════════════════════════

class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BillStatus(Enum):
    PENDING = "Pending"
    VALIDATED = "Validated"
    FLAGGED = "Flagged"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class ErrorType(Enum):
    PRICE_MISMATCH = "Price Mismatch"
    TAX_ERROR = "Tax Error"
    TOTAL_MISMATCH = "Total Mismatch"
    DUPLICATE_BILL = "Duplicate Bill"
    MISSING_DATA = "Missing Data"
    QUANTITY_ERROR = "Quantity Error"


# ═════════════════════════════════════════════════════════════════════════════
#  CUSTOM EXCEPTIONS
# ═════════════════════════════════════════════════════════════════════════════

class ValidationError(Exception):
    """Custom exception for billing validation errors."""
    def __init__(self, message, error_type=ErrorType.MISSING_DATA, severity=Severity.ERROR):
        super().__init__(message)
        self.error_type = error_type
        self.severity = severity

    def __str__(self):
        return f"[{self.severity.value}] {self.error_type.value}: {super().__str__()}"


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


# ═════════════════════════════════════════════════════════════════════════════
#  DECORATORS
# ═════════════════════════════════════════════════════════════════════════════

def log_action(func):
    """Decorator — logs function entry, exit, and errors."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"→ {func.__name__}()")
        try:
            result = func(*args, **kwargs)
            logger.info(f"✓ {func.__name__}() done")
            return result
        except Exception as e:
            logger.error(f"✗ {func.__name__}() failed: {e}")
            raise
    return wrapper


def db_transaction(func):
    """Decorator — wraps DB function in commit/rollback."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try: 
            result = func(self, *args, **kwargs)
            self.conn.commit()
            return result
        except Exception as e:
            self.conn.rollback()
            raise
    return wrapper


# ═════════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def format_currency(amount):
    """Format number as ₹X,XX,XXX.XX (Indian format)."""
    if amount is None:
        return "₹0.00"
    try:
        amount = float(amount)
        sign = "-" if amount < 0 else ""
        amount = abs(amount)
        integer_part = int(amount)
        decimal = f"{amount - integer_part:.2f}"[1:]

        s = str(integer_part)
        if len(s) <= 3:
            formatted = s
        else:
            last3 = s[-3:]
            rest = s[:-3]
            groups = []
            while rest:
                groups.append(rest[-2:])
                rest = rest[:-2]
            groups.reverse()
            formatted = ",".join(groups) + "," + last3
        return f"{sign}₹{formatted}{decimal}"
    except (ValueError, TypeError):
        return "₹0.00"


def pct(part, whole):
    """Safe percentage calculation."""
    return round((part / whole) * 100, 2) if whole else 0.0


# ═════════════════════════════════════════════════════════════════════════════
#  DATA MODELS (OOP, Properties, Magic Methods, Composition)
# ═════════════════════════════════════════════════════════════════════════════

class Product:
    """Product in the catalog. Demonstrates: Encapsulation, Properties."""

    def __init__(self, product_id=None, name="", category="",
                 unit_price=0.0, tax_rate=0.0):
        self._product_id = product_id
        self._name = name
        self._category = category
        self._unit_price = float(unit_price)
        self._tax_rate = float(tax_rate)

    # Properties with validation
    @property
    def product_id(self):
        return self._product_id

    @product_id.setter
    def product_id(self, val):
        self._product_id = val

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val):
        if not val or not val.strip():
            raise ValueError("Product name cannot be empty")
        self._name = val.strip()

    @property
    def category(self):
        return self._category

    @property
    def unit_price(self):
        return self._unit_price

    @unit_price.setter
    def unit_price(self, val):
        val = float(val)
        if val < 0:
            raise ValueError("Price cannot be negative")
        self._unit_price = val

    @property
    def tax_rate(self):
        return self._tax_rate

    @tax_rate.setter
    def tax_rate(self, val):
        val = float(val)
        if not (0 <= val <= 100):
            raise ValueError("Tax rate must be 0-100")
        self._tax_rate = val

    def calculate_tax(self, quantity=1):
        return round(self._unit_price * quantity * (self._tax_rate / 100), 2)

    def __str__(self):
        return f"{self._name} (₹{self._unit_price:.2f}, {self._tax_rate}%)"

    def __repr__(self):
        return f"Product(id={self._product_id}, name={self._name!r})"

    def __eq__(self, other):
        if not isinstance(other, Product):
            return NotImplemented
        return self._product_id == other._product_id

    def to_dict(self):
        return {"product_id": self._product_id, "name": self._name,
                "category": self._category, "unit_price": self._unit_price,
                "tax_rate": self._tax_rate}


class BillItem:
    """Single line item in a bill. Demonstrates: Encapsulation, Calculated Properties."""

    def __init__(self, item_id=None, bill_id=None, product_id=None,
                 product_name="", quantity=1, unit_price=0.0,
                 tax_amount=0.0, line_total=0.0):
        self._item_id = item_id
        self._bill_id = bill_id
        self._product_id = product_id
        self._product_name = product_name
        self._quantity = int(quantity)
        self._unit_price = float(unit_price)
        self._tax_amount = float(tax_amount)
        self._line_total = float(line_total)

    @property
    def item_id(self):
        return self._item_id

    @property
    def bill_id(self):
        return self._bill_id

    @bill_id.setter
    def bill_id(self, val):
        self._bill_id = val

    @property
    def product_id(self):
        return self._product_id

    @property
    def product_name(self):
        return self._product_name

    @property
    def quantity(self):
        return self._quantity

    @quantity.setter
    def quantity(self, val):
        val = int(val)
        if val <= 0:
            raise ValueError("Quantity must be positive")
        self._quantity = val

    @property
    def unit_price(self):
        return self._unit_price

    @property
    def tax_amount(self):
        return self._tax_amount

    @property
    def line_total(self):
        return self._line_total

    @property
    def subtotal(self):
        return round(self._unit_price * self._quantity, 2)

    def __str__(self):
        return f"{self._product_name}: {self._quantity} × ₹{self._unit_price:.2f} = ₹{self._line_total:.2f}"

    def __repr__(self):
        return f"BillItem(product={self._product_name!r}, qty={self._quantity})"

    def to_dict(self):
        return {"item_id": self._item_id, "product_id": self._product_id,
                "product_name": self._product_name, "quantity": self._quantity,
                "unit_price": self._unit_price, "tax_amount": self._tax_amount,
                "line_total": self._line_total}


class Bill:
    """
    Complete bill with line items.
    Demonstrates: Composition (has-a BillItem), Aggregation, Magic Methods.
    """

    def __init__(self, bill_id=None, bill_number="", vendor_name="",
                 bill_date=None, total_amount=0.0,
                 status=BillStatus.PENDING, created_at=None):
        self._bill_id = bill_id
        self._bill_number = bill_number
        self._vendor_name = vendor_name
        self._bill_date = bill_date or datetime.now().strftime("%Y-%m-%d")
        self._total_amount = float(total_amount)
        self._status = status if isinstance(status, BillStatus) else BillStatus(status)
        self._created_at = created_at
        self._items = []  # Composition: Bill HAS-A list of BillItems

    @property
    def bill_id(self):
        return self._bill_id

    @bill_id.setter
    def bill_id(self, val):
        self._bill_id = val

    @property
    def bill_number(self):
        return self._bill_number

    @property
    def vendor_name(self):
        return self._vendor_name

    @property
    def bill_date(self):
        return self._bill_date

    @property
    def total_amount(self):
        return self._total_amount

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, val):
        self._status = val if isinstance(val, BillStatus) else BillStatus(val)

    @property
    def items(self):
        return self._items.copy()

    @property
    def item_count(self):
        return len(self._items)

    def add_item(self, item):
        """Add a BillItem (Composition)."""
        if not isinstance(item, BillItem):
            raise TypeError("Can only add BillItem objects")
        item.bill_id = self._bill_id
        self._items.append(item)

    @property
    def calculated_total(self):
        """Aggregation: sum of all line totals."""
        return round(sum(i.line_total for i in self._items), 2)

    @property
    def total_discrepancy(self):
        return round(self._total_amount - self.calculated_total, 2)

    # Magic Methods
    def __str__(self):
        return f"Bill #{self._bill_number} | {self._vendor_name} | ₹{self._total_amount:.2f}"

    def __repr__(self):
        return f"Bill(number={self._bill_number!r}, items={self.item_count})"

    def __len__(self):
        return len(self._items)

    def __eq__(self, other):
        if not isinstance(other, Bill):
            return NotImplemented
        return self._bill_id == other._bill_id

    def to_dict(self):
        return {
            "bill_id": self._bill_id, "bill_number": self._bill_number,
            "vendor_name": self._vendor_name, "bill_date": self._bill_date,
            "total_amount": self._total_amount, "status": self._status.value,
            "created_at": self._created_at, "item_count": self.item_count,
            "calculated_total": self.calculated_total,
            "discrepancy": self.total_discrepancy,
            "items": [i.to_dict() for i in self._items]
        }


# ═════════════════════════════════════════════════════════════════════════════
#  DATABASE (SQLite, CRUD, Aggregation — GROUP BY, SUM, AVG, COUNT)
# ═════════════════════════════════════════════════════════════════════════════

class Database:
    """SQLite database with schema, CRUD, and analytics queries."""

    def __init__(self, db_path=None):
        self._path = db_path or DB_PATH
        self.conn = sqlite3.connect(self._path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cur = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                product_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                category    TEXT DEFAULT '',
                unit_price  REAL DEFAULT 0.0,
                tax_rate    REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS bills (
                bill_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_number  TEXT NOT NULL UNIQUE,
                vendor_name  TEXT DEFAULT '',
                bill_date    TEXT NOT NULL,
                total_amount REAL DEFAULT 0.0,
                status       TEXT DEFAULT 'Pending',
                created_at   TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS bill_items (
                item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id      INTEGER NOT NULL,
                product_id   INTEGER,
                product_name TEXT DEFAULT '',
                quantity     INTEGER DEFAULT 1,
                unit_price   REAL DEFAULT 0.0,
                tax_amount   REAL DEFAULT 0.0,
                line_total   REAL DEFAULT 0.0,
                FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS validation_logs (
                log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id    INTEGER NOT NULL,
                error_type TEXT NOT NULL,
                severity   TEXT DEFAULT 'INFO',
                message    TEXT DEFAULT '',
                timestamp  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    # ── Product CRUD ──

    @db_transaction
    def add_product(self, p):
        self.cur.execute("INSERT INTO products (name,category,unit_price,tax_rate) VALUES (?,?,?,?)",
                         (p.name, p.category, p.unit_price, p.tax_rate))
        p.product_id = self.cur.lastrowid
        return p.product_id

    @db_transaction
    def update_product(self, p):
        self.cur.execute("UPDATE products SET name=?, category=?, unit_price=?, tax_rate=? WHERE product_id=?",
                         (p.name, p.category, p.unit_price, p.tax_rate, p.product_id))

    @db_transaction
    def delete_product(self, pid):
        self.cur.execute("DELETE FROM products WHERE product_id=?", (pid,))

    def get_product(self, pid):
        self.cur.execute("SELECT * FROM products WHERE product_id=?", (pid,))
        r = self.cur.fetchone()
        return Product(r["product_id"], r["name"], r["category"],
                       r["unit_price"], r["tax_rate"]) if r else None

    def get_all_products(self):
        self.cur.execute("SELECT * FROM products ORDER BY name")
        return [Product(r["product_id"], r["name"], r["category"],
                        r["unit_price"], r["tax_rate"]) for r in self.cur.fetchall()]

    def search_products(self, q):
        self.cur.execute("SELECT * FROM products WHERE name LIKE ? ORDER BY name", (f"%{q}%",))
        return [Product(r["product_id"], r["name"], r["category"],
                        r["unit_price"], r["tax_rate"]) for r in self.cur.fetchall()]

    def get_categories(self):
        self.cur.execute("SELECT DISTINCT category FROM products ORDER BY category")
        return [r["category"] for r in self.cur.fetchall()]

    # ── Bill CRUD ──

    @db_transaction
    def add_bill(self, bill):
        self.cur.execute(
            "INSERT INTO bills (bill_number,vendor_name,bill_date,total_amount,status) VALUES (?,?,?,?,?)",
            (bill.bill_number, bill.vendor_name, bill.bill_date,
             bill.total_amount, bill.status.value))
        bid = self.cur.lastrowid
        bill.bill_id = bid
        for item in bill.items:
            self.cur.execute(
                "INSERT INTO bill_items (bill_id,product_id,product_name,quantity,unit_price,tax_amount,line_total) VALUES (?,?,?,?,?,?,?)",
                (bid, item.product_id, item.product_name, item.quantity,
                 item.unit_price, item.tax_amount, item.line_total))
        return bid

    @db_transaction
    def update_bill_status(self, bid, status):
        val = status.value if isinstance(status, BillStatus) else status
        self.cur.execute("UPDATE bills SET status=? WHERE bill_id=?", (val, bid))

    @db_transaction
    def delete_bill(self, bid):
        self.cur.execute("DELETE FROM bills WHERE bill_id=?", (bid,))

    def get_bill(self, bid):
        self.cur.execute("SELECT * FROM bills WHERE bill_id=?", (bid,))
        r = self.cur.fetchone()
        if not r:
            return None
        bill = Bill(r["bill_id"], r["bill_number"], r["vendor_name"],
                    r["bill_date"], r["total_amount"], r["status"], r["created_at"])
        for item in self._get_items(bid):
            bill.add_item(item)
        return bill

    def get_all_bills(self, limit=100):
        self.cur.execute("SELECT * FROM bills ORDER BY bill_date DESC LIMIT ?", (limit,))
        return [Bill(r["bill_id"], r["bill_number"], r["vendor_name"],
                     r["bill_date"], r["total_amount"], r["status"], r["created_at"])
                for r in self.cur.fetchall()]

    def get_bills_by_status(self, status):
        val = status.value if isinstance(status, BillStatus) else status
        self.cur.execute("SELECT * FROM bills WHERE status=? ORDER BY bill_date DESC", (val,))
        return [Bill(r["bill_id"], r["bill_number"], r["vendor_name"],
                     r["bill_date"], r["total_amount"], r["status"])
                for r in self.cur.fetchall()]

    def get_bills_by_vendor(self, vendor):
        self.cur.execute("SELECT * FROM bills WHERE vendor_name=? ORDER BY bill_date DESC", (vendor,))
        return [Bill(r["bill_id"], r["bill_number"], r["vendor_name"],
                     r["bill_date"], r["total_amount"], r["status"])
                for r in self.cur.fetchall()]

    def search_bills(self, q):
        self.cur.execute("SELECT * FROM bills WHERE bill_number LIKE ? OR vendor_name LIKE ? ORDER BY bill_date DESC",
                         (f"%{q}%", f"%{q}%"))
        return [Bill(r["bill_id"], r["bill_number"], r["vendor_name"],
                     r["bill_date"], r["total_amount"], r["status"])
                for r in self.cur.fetchall()]

    def bill_exists(self, bill_number, exclude_id=None):
        if exclude_id:
            self.cur.execute("SELECT COUNT(*) as c FROM bills WHERE bill_number=? AND bill_id!=?",
                             (bill_number, exclude_id))
        else:
            self.cur.execute("SELECT COUNT(*) as c FROM bills WHERE bill_number=?", (bill_number,))
        return self.cur.fetchone()["c"] > 0

    def _get_items(self, bid):
        self.cur.execute("SELECT * FROM bill_items WHERE bill_id=? ORDER BY item_id", (bid,))
        return [BillItem(r["item_id"], r["bill_id"], r["product_id"],
                         r["product_name"], r["quantity"], r["unit_price"],
                         r["tax_amount"], r["line_total"])
                for r in self.cur.fetchall()]

    # ── Validation Logs ──

    @db_transaction
    def add_log(self, bid, error_type, severity, message):
        et = error_type.value if isinstance(error_type, ErrorType) else error_type
        sv = severity.value if isinstance(severity, Severity) else severity
        self.cur.execute("INSERT INTO validation_logs (bill_id,error_type,severity,message) VALUES (?,?,?,?)",
                         (bid, et, sv, message))

    def get_logs(self, bid):
        self.cur.execute("SELECT * FROM validation_logs WHERE bill_id=? ORDER BY timestamp DESC", (bid,))
        return [dict(r) for r in self.cur.fetchall()]

    @db_transaction
    def clear_logs(self, bid):
        self.cur.execute("DELETE FROM validation_logs WHERE bill_id=?", (bid,))

    # ── Analytics Queries (Aggregation: SUM, AVG, COUNT, GROUP BY) ──

    def count_bills(self):
        self.cur.execute("SELECT COUNT(*) as c FROM bills")
        return self.cur.fetchone()["c"]

    def total_amount(self):
        self.cur.execute("SELECT COALESCE(SUM(total_amount),0) as t FROM bills")
        return self.cur.fetchone()["t"]

    def total_errors(self):
        self.cur.execute("SELECT COUNT(*) as c FROM validation_logs WHERE severity IN ('ERROR','CRITICAL')")
        return self.cur.fetchone()["c"]

    def status_breakdown(self):
        self.cur.execute("SELECT status, COUNT(*) as c FROM bills GROUP BY status")
        return {r["status"]: r["c"] for r in self.cur.fetchall()}

    def spending_by_category(self):
        self.cur.execute("""
            SELECT COALESCE(p.category,'Uncategorized') as category,
                   SUM(bi.line_total) as total, COUNT(DISTINCT bi.bill_id) as bills
            FROM bill_items bi LEFT JOIN products p ON bi.product_id=p.product_id
            GROUP BY category ORDER BY total DESC
        """)
        return [dict(r) for r in self.cur.fetchall()]

    def spending_by_vendor(self):
        self.cur.execute("""
            SELECT vendor_name, SUM(total_amount) as total,
                   COUNT(*) as bills, AVG(total_amount) as avg_bill
            FROM bills GROUP BY vendor_name ORDER BY total DESC
        """)
        return [dict(r) for r in self.cur.fetchall()]

    def error_distribution(self):
        self.cur.execute("SELECT error_type, COUNT(*) as c FROM validation_logs GROUP BY error_type ORDER BY c DESC")
        return {r["error_type"]: r["c"] for r in self.cur.fetchall()}

    def vendor_error_rates(self):
        self.cur.execute("""
            SELECT b.vendor_name, COUNT(DISTINCT b.bill_id) as total_bills,
                   COUNT(vl.log_id) as errors
            FROM bills b LEFT JOIN validation_logs vl ON b.bill_id=vl.bill_id
            GROUP BY b.vendor_name ORDER BY errors DESC
        """)
        return [dict(r) for r in self.cur.fetchall()]

    def monthly_spending(self):
        self.cur.execute("""
            SELECT strftime('%%Y-%%m', bill_date) as month,
                   SUM(total_amount) as total, COUNT(*) as bills
            FROM bills GROUP BY month ORDER BY month
        """)
        return [dict(r) for r in self.cur.fetchall()]

    def price_history(self, pid):
        self.cur.execute("""
            SELECT bi.unit_price, b.bill_date FROM bill_items bi
            JOIN bills b ON bi.bill_id=b.bill_id WHERE bi.product_id=? ORDER BY b.bill_date
        """, (pid,))
        return [dict(r) for r in self.cur.fetchall()]

    def potential_savings(self):
        self.cur.execute("""
            SELECT bi.product_name, bi.unit_price as billed, p.unit_price as catalog,
                   bi.quantity, (bi.unit_price - p.unit_price)*bi.quantity as overpay
            FROM bill_items bi JOIN products p ON bi.product_id=p.product_id
            WHERE bi.unit_price > p.unit_price
        """)
        rows = self.cur.fetchall()
        return {"items": [dict(r) for r in rows],
                "total": sum(r["overpay"] for r in rows)}

    def close(self):
        self.conn.close()


# ═════════════════════════════════════════════════════════════════════════════
#  VALIDATORS (ABC, Inheritance, Polymorphism)
# ═════════════════════════════════════════════════════════════════════════════

class BaseValidator(ABC):
    """Abstract Base Class — all validators inherit from this."""
    def __init__(self, name):
        self._name = name
        self._results = []

    @abstractmethod
    def validate(self, bill, db=None):
        pass

    def _add(self, check, passed, msg, severity=Severity.INFO, error_type=None):
        self._results.append({
            "check": check, "passed": passed, "message": msg,
            "severity": severity.value,
            "error_type": error_type.value if error_type else None
        })

    def clear(self):
        self._results = []


class PriceValidator(BaseValidator):
    """Checks billed prices against catalog. Inherits BaseValidator."""
    def __init__(self):
        super().__init__("Price Validator")

    def validate(self, bill, db=None):
        self.clear()
        if not db:
            return self._results
        for item in bill.items:
            if not item.product_id:
                continue
            product = db.get_product(item.product_id)
            if not product or product.unit_price == 0:
                continue
            diff = abs(item.unit_price - product.unit_price) / product.unit_price * 100
            if diff <= 5:
                self._add(f"Price: {item.product_name}", True,
                          f"Price OK (₹{item.unit_price:.2f})")
            else:
                direction = "overcharged" if item.unit_price > product.unit_price else "undercharged"
                self._add(f"Price: {item.product_name}", False,
                          f"Billed ₹{item.unit_price:.2f} vs Catalog ₹{product.unit_price:.2f} ({direction} {diff:.1f}%)",
                          Severity.ERROR, ErrorType.PRICE_MISMATCH)
        return self._results


class TaxValidator(BaseValidator):
    """Checks tax calculations. Inherits BaseValidator."""
    def __init__(self):
        super().__init__("Tax Validator")

    def validate(self, bill, db=None):
        self.clear()
        if not db:
            return self._results
        for item in bill.items:
            if not item.product_id:
                continue
            product = db.get_product(item.product_id)
            if not product:
                continue
            expected = round(item.unit_price * item.quantity * (product.tax_rate / 100), 2)
            diff = abs(item.tax_amount - expected)
            if diff <= 1.0:
                self._add(f"Tax: {item.product_name}", True,
                          f"Tax OK at {product.tax_rate}% (₹{item.tax_amount:.2f})")
            else:
                self._add(f"Tax: {item.product_name}", False,
                          f"Expected ₹{expected:.2f} tax but billed ₹{item.tax_amount:.2f} (off by ₹{diff:.2f})",
                          Severity.ERROR, ErrorType.TAX_ERROR)
        return self._results


class TotalValidator(BaseValidator):
    """Checks stated total vs calculated total. Inherits BaseValidator."""
    def __init__(self):
        super().__init__("Total Validator")

    def validate(self, bill, db=None):
        self.clear()
        if not bill.items:
            self._add("Total Check", False, "No line items", Severity.WARNING, ErrorType.MISSING_DATA)
            return self._results
        diff = abs(bill.total_amount - bill.calculated_total)
        if diff <= 2.0:
            self._add("Total Check", True, f"Total matches (₹{bill.total_amount:.2f})")
        else:
            self._add("Total Check", False,
                      f"Stated ₹{bill.total_amount:.2f} vs Calculated ₹{bill.calculated_total:.2f} (off by ₹{diff:.2f})",
                      Severity.ERROR, ErrorType.TOTAL_MISMATCH)
        return self._results


class DuplicateDetector(BaseValidator):
    """Detects duplicate bill numbers. Inherits BaseValidator."""
    def __init__(self):
        super().__init__("Duplicate Detector")

    def validate(self, bill, db=None):
        self.clear()
        if not db:
            return self._results
        if db.bill_exists(bill.bill_number, exclude_id=bill.bill_id):
            self._add("Duplicate Check", False,
                      f"Bill number '{bill.bill_number}' already exists!",
                      Severity.CRITICAL, ErrorType.DUPLICATE_BILL)
        else:
            self._add("Duplicate Check", True, "No duplicate found")
        return self._results


class CompletenessValidator(BaseValidator):
    """Checks required fields are present. Inherits BaseValidator."""
    def __init__(self):
        super().__init__("Completeness Validator")

    def validate(self, bill, db=None):
        self.clear()
        for field, val in [("Bill Number", bill.bill_number),
                           ("Vendor", bill.vendor_name),
                           ("Date", bill.bill_date)]:
            if val and str(val).strip():
                self._add(f"Required: {field}", True, f"{field} present")
            else:
                self._add(f"Required: {field}", False, f"{field} is missing",
                          Severity.ERROR, ErrorType.MISSING_DATA)
        if not bill.items:
            self._add("Line Items", False, "No line items", Severity.ERROR, ErrorType.MISSING_DATA)
        else:
            self._add("Line Items", True, f"{bill.item_count} item(s)")
        return self._results


class BillValidator:
    """
    Orchestrates all validators (Polymorphism — calls validate() on different types).
    """
    def __init__(self, db):
        self._db = db
        # Polymorphism: different validator types, same interface
        self._validators = [
            CompletenessValidator(),
            PriceValidator(),
            TaxValidator(),
            TotalValidator(),
            DuplicateDetector(),
        ]

    @log_action
    def validate(self, bill):
        all_results = []
        for v in self._validators:
            all_results.extend(v.validate(bill, self._db))

        errors = [r for r in all_results if not r["passed"] and r["severity"] in ("ERROR", "CRITICAL")]
        warnings = [r for r in all_results if not r["passed"] and r["severity"] == "WARNING"]
        passed = len(errors) == 0

        # Log to DB
        if bill.bill_id:
            self._db.clear_logs(bill.bill_id)
            for r in all_results:
                if not r["passed"]:
                    self._db.add_log(bill.bill_id, r["error_type"] or "Unknown",
                                     r["severity"], r["message"])
            if passed and not warnings:
                self._db.update_bill_status(bill.bill_id, BillStatus.VALIDATED)
            elif not passed:
                self._db.update_bill_status(bill.bill_id, BillStatus.FLAGGED)

        return {
            "results": all_results, "passed": passed,
            "total": len(all_results),
            "passed_count": len([r for r in all_results if r["passed"]]),
            "errors": len(errors), "warnings": len(warnings),
            "summary": (f"✓ All {len(all_results)} checks passed." if passed
                        else f"✗ {len(errors)} error(s), {len(warnings)} warning(s) found.")
        }


# ═════════════════════════════════════════════════════════════════════════════
#  ANALYTICS ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class AnalyticsEngine:
    """Analyzes billing data for decision support."""

    def __init__(self, db):
        self._db = db

    def dashboard_stats(self):
        savings = self._db.potential_savings()
        return {
            "total_bills": self._db.count_bills(),
            "total_amount": self._db.total_amount(),
            "total_amount_fmt": format_currency(self._db.total_amount()),
            "total_errors": self._db.total_errors(),
            "total_savings": savings["total"],
            "total_savings_fmt": format_currency(savings["total"]),
            "status_breakdown": self._db.status_breakdown()
        }

    def category_report(self):
        data = self._db.spending_by_category()
        total = sum(r["total"] or 0 for r in data)
        return [{"category": r["category"], "total": r["total"] or 0,
                 "total_fmt": format_currency(r["total"]),
                 "bills": r["bills"], "pct": pct(r["total"] or 0, total)}
                for r in data]

    def vendor_report(self):
        vendors = self._db.spending_by_vendor()
        errors = self._db.vendor_error_rates()
        err_map = {e["vendor_name"]: e["errors"] for e in errors}
        result = []
        for v in vendors:
            errs = err_map.get(v["vendor_name"], 0)
            bills = v["bills"]
            reliability = 100 - pct(errs, bills)
            result.append({
                "vendor": v["vendor_name"], "bills": bills,
                "total": v["total"], "total_fmt": format_currency(v["total"]),
                "avg_fmt": format_currency(v["avg_bill"]),
                "errors": errs, "reliability": round(reliability, 1),
                "rating": self._rate(reliability)
            })
        return result

    def monthly_report(self):
        data = self._db.monthly_spending()
        if not data:
            return []
        mx = max(r["total"] for r in data)
        return [{"month": r["month"], "total": r["total"],
                 "total_fmt": format_currency(r["total"]),
                 "bills": r["bills"],
                 "bar_pct": round(r["total"] / mx * 100) if mx else 0}
                for r in data]

    def error_report(self):
        dist = self._db.error_distribution()
        total = sum(dist.values()) if dist else 0
        return {"total": total,
                "breakdown": [{"type": t, "count": c, "pct": pct(c, total)}
                              for t, c in sorted(dist.items(), key=lambda x: x[1], reverse=True)]}

    def price_report(self):
        products = self._db.get_all_products()
        result = []
        for p in products:
            history = self._db.price_history(p.product_id)
            if not history:
                continue
            prices = [h["unit_price"] for h in history]
            avg_p = sum(prices) / len(prices)
            volatility = ((max(prices) - min(prices)) / avg_p * 100) if avg_p else 0
            result.append({
                "product": p.name, "category": p.category,
                "catalog": p.unit_price, "catalog_fmt": format_currency(p.unit_price),
                "min": min(prices), "min_fmt": format_currency(min(prices)),
                "max": max(prices), "max_fmt": format_currency(max(prices)),
                "avg": round(avg_p, 2), "avg_fmt": format_currency(avg_p),
                "volatility": round(volatility, 1),
                "flag": volatility > 20
            })
        result.sort(key=lambda x: x["volatility"], reverse=True)
        return result

    def recommendations(self):
        recos = []
        try:
            for v in self.vendor_report():
                if v["reliability"] < 70:
                    recos.append({"icon": "⚠️", "priority": "HIGH",
                                  "title": f"Unreliable Vendor: {v['vendor']}",
                                  "msg": f"{v['errors']} errors in {v['bills']} bills ({v['reliability']}% reliability)",
                                  "impact": f"{v['errors']} errors"})
            savings = self._db.potential_savings()
            if savings["total"] > 0:
                recos.append({"icon": "💰", "priority": "HIGH",
                              "title": "Savings Available",
                              "msg": f"You were overcharged on {len(savings['items'])} items. Total: {format_currency(savings['total'])}",
                              "impact": format_currency(savings["total"])})
            pending = self._db.status_breakdown().get("Pending", 0)
            if pending > 3:
                recos.append({"icon": "⏳", "priority": "MEDIUM",
                              "title": f"{pending} Bills Pending Review",
                              "msg": "Run validation to catch errors early.",
                              "impact": f"{pending} bills"})
            if not recos:
                recos.append({"icon": "✅", "priority": "LOW",
                              "title": "All Good!", "msg": "No issues found.",
                              "impact": "None"})
        except Exception:
            recos.append({"icon": "ℹ️", "priority": "LOW",
                          "title": "Add Data", "msg": "Add bills to see analytics.",
                          "impact": "—"})
        return recos

    def _rate(self, rel):
        if rel >= 90: return "★★★★★"
        if rel >= 75: return "★★★★☆"
        if rel >= 60: return "★★★☆☆"
        if rel >= 40: return "★★☆☆☆"
        return "★☆☆☆☆"


# ═════════════════════════════════════════════════════════════════════════════
#  SAMPLE DATA SEEDER
# ═════════════════════════════════════════════════════════════════════════════

def seed_database(db):
    """Populate DB with sample data for demo."""
    if db.count_bills() > 0:
        print("[i] Database already has data, skipping seed.")
        return

    print("[*] Seeding sample data...")

    products = [
        Product(name="Laptop Charger", category="Electronics", unit_price=1200, tax_rate=18),
        Product(name="USB Cable", category="Electronics", unit_price=250, tax_rate=18),
        Product(name="Wireless Mouse", category="Electronics", unit_price=650, tax_rate=18),
        Product(name="Keyboard", category="Electronics", unit_price=900, tax_rate=18),
        Product(name="A4 Paper Ream", category="Stationery", unit_price=350, tax_rate=12),
        Product(name="Printer Ink", category="Stationery", unit_price=800, tax_rate=12),
        Product(name="Notebook Pack", category="Stationery", unit_price=180, tax_rate=12),
        Product(name="Pen Box (10)", category="Stationery", unit_price=120, tax_rate=12),
        Product(name="Tea Bags (100)", category="Food", unit_price=220, tax_rate=5),
        Product(name="Coffee 500g", category="Food", unit_price=450, tax_rate=5),
        Product(name="Office Chair", category="Furniture", unit_price=5500, tax_rate=18),
        Product(name="Desk Lamp", category="Furniture", unit_price=1200, tax_rate=18),
        Product(name="Internet Bill", category="Services", unit_price=999, tax_rate=18),
        Product(name="Cleaning Service", category="Services", unit_price=2000, tax_rate=18),
    ]
    for p in products:
        db.add_product(p)

    vendors = ["TechMart India", "Kumar Stationery", "Reliance Digital",
               "Balaji Traders", "Sharma & Sons", "QuickSupply Co."]

    random.seed(42)
    base = datetime(2026, 1, 15)

    for i in range(20):
        date = base + timedelta(days=random.randint(0, 200))
        vendor = random.choice(vendors)
        selected = random.sample(products, random.randint(2, 5))

        items = []
        total = 0.0
        for prod in selected:
            qty = random.randint(1, 8)
            # Sometimes overcharge (for demo errors)
            price = prod.unit_price * random.uniform(1.1, 1.3) if random.random() < 0.2 else prod.unit_price
            price = round(price, 2)
            # Sometimes wrong tax
            rate = prod.tax_rate + random.choice([-5, 5]) if random.random() < 0.15 else prod.tax_rate
            tax = round(price * qty * (rate / 100), 2)
            lt = round(price * qty + tax, 2)
            total += lt
            items.append(BillItem(product_id=prod.product_id, product_name=prod.name,
                                  quantity=qty, unit_price=price, tax_amount=tax, line_total=lt))

        # Sometimes mess up the total too
        if random.random() < 0.1:
            total = round(total * random.uniform(0.9, 1.1), 2)
        else:
            total = round(total, 2)

        bill = Bill(bill_number=f"INV-2026-{1001+i}", vendor_name=vendor,
                    bill_date=date.strftime("%Y-%m-%d"), total_amount=total)
        for item in items:
            bill.add_item(item)
        db.add_bill(bill)

    print(f"[+] Seeded {len(products)} products, 20 bills")


# ═════════════════════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ═════════════════════════════════════════════════════════════════════════════

db = Database()
analytics = AnalyticsEngine(db)


@app.route("/")
def index():
    return render_template("index.html")


# ── Dashboard ──

@app.route("/api/dashboard")
def api_dashboard():
    stats = analytics.dashboard_stats()
    bills = db.get_all_bills(10)
    recos = analytics.recommendations()
    return jsonify({
        "stats": stats,
        "recent_bills": [b.to_dict() for b in bills],
        "recommendations": recos
    })


# ── Bills ──,,,,

@app.route("/api/bills")
def api_bills():
    q = request.args.get("q", "")
    bills = db.search_bills(q) if q else db.get_all_bills()
    return jsonify([b.to_dict() for b in bills])


@app.route("/api/bills", methods=["POST"])
def api_add_bill():
    data = request.json
    bill = Bill(bill_number=data["bill_number"], vendor_name=data["vendor_name"],
                bill_date=data.get("bill_date", datetime.now().strftime("%Y-%m-%d")),
                total_amount=float(data.get("total_amount", 0)))

    for it in data.get("items", []):
        item = BillItem(product_id=it.get("product_id"), product_name=it["product_name"],
                        quantity=int(it.get("quantity", 1)),
                        unit_price=float(it.get("unit_price", 0)),
                        tax_amount=float(it.get("tax_amount", 0)),
                        line_total=float(it.get("line_total", 0)))
        bill.add_item(item)

    try:
        bid = db.add_bill(bill)
        # Auto-validate
        bill = db.get_bill(bid)
        validator = BillValidator(db)
        result = validator.validate(bill)
        bill = db.get_bill(bid)  # Reload with updated status
        return jsonify({"bill": bill.to_dict(), "validation": result}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/bills/<int:bid>")
def api_get_bill(bid):
    bill = db.get_bill(bid)
    if not bill:
        return jsonify({"error": "Not found"}), 404
    logs = db.get_logs(bid)
    return jsonify({"bill": bill.to_dict(), "logs": logs})


@app.route("/api/bills/<int:bid>/validate", methods=["POST"])
def api_validate_bill(bid):
    bill = db.get_bill(bid)
    if not bill:
        return jsonify({"error": "Not found"}), 404
    validator = BillValidator(db)
    result = validator.validate(bill)
    bill = db.get_bill(bid)
    return jsonify({"bill": bill.to_dict(), "validation": result})


@app.route("/api/bills/<int:bid>/status", methods=["PUT"])
def api_update_status(bid):
    status = request.json.get("status")
    db.update_bill_status(bid, status)
    return jsonify({"ok": True})


@app.route("/api/bills/<int:bid>", methods=["DELETE"])
def api_delete_bill(bid):
    db.delete_bill(bid)
    return jsonify({"ok": True})


# ── Products ──

@app.route("/api/products")
def api_products():
    q = request.args.get("q", "")
    cat = request.args.get("category", "")
    if q:
        prods = db.search_products(q)
    elif cat:
        prods = [p for p in db.get_all_products() if p.category == cat]
    else:
        prods = db.get_all_products()
    return jsonify({"products": [p.to_dict() for p in prods],
                    "categories": db.get_categories()})


@app.route("/api/products", methods=["POST"])
def api_add_product():
    d = request.json
    p = Product(name=d["name"], category=d.get("category", ""),
                unit_price=float(d.get("unit_price", 0)),
                tax_rate=float(d.get("tax_rate", 0)))
    db.add_product(p)
    return jsonify(p.to_dict()), 201


@app.route("/api/products/<int:pid>", methods=["PUT"])
def api_update_product(pid):
    d = request.json
    p = Product(product_id=pid, name=d["name"], category=d.get("category", ""),
                unit_price=float(d.get("unit_price", 0)),
                tax_rate=float(d.get("tax_rate", 0)))
    db.update_product(p)
    return jsonify(p.to_dict())


@app.route("/api/products/<int:pid>", methods=["DELETE"])
def api_delete_product(pid):
    db.delete_product(pid)
    return jsonify({"ok": True})


# ── Reports ──

@app.route("/api/reports/<report_type>")
def api_report(report_type):
    try:
        if report_type == "category":
            return jsonify(analytics.category_report())
        elif report_type == "vendor":
            return jsonify(analytics.vendor_report())
        elif report_type == "monthly":
            return jsonify(analytics.monthly_report())
        elif report_type == "errors":
            return jsonify(analytics.error_report())
        elif report_type == "price":
            return jsonify(analytics.price_report())
        else:
            return jsonify({"error": "Unknown report type"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Validate All Pending ──

@app.route("/api/validate-all", methods=["POST"])
def api_validate_all():
    pending = db.get_bills_by_status(BillStatus.PENDING)
    validator = BillValidator(db)
    ok, flagged = 0, 0
    for b in pending:
        bill = db.get_bill(b.bill_id)
        if bill:
            r = validator.validate(bill)
            if r["passed"]:
                ok += 1
            else:
                flagged += 1
    return jsonify({"validated": ok, "flagged": flagged, "total": len(pending)})


# ═════════════════════════════════════════════════════════════════════════════
#  RUN
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    seed_database(db)
    print("\n[OK] Starting Smart Billing Validator...")
    print("[OK] Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
