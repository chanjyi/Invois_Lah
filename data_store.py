"""Local SQLite persistence. Deliberately no public anonymous backend."""
from __future__ import annotations
import os
from pathlib import Path
import sqlite3
from uuid import uuid4
from datetime import datetime

DATA_DIR = Path(os.environ.get('INVOISLAH_DATA_DIR', Path(__file__).parent / 'data')).resolve()
DB_PATH = DATA_DIR / 'invoislah.db'

PROFILE_FIELDS = [
    'name', 'email', 'phone', 'tin', 'id_type', 'id_number', 'msic', 'activity',
    'sst_number', 'address', 'city', 'postcode', 'state_code', 'country_code',
]
INVOICE_FIELDS = [
    'invoice_number', 'client_name', 'client_tin', 'client_id_type',
    'client_id_number', 'client_email', 'client_phone', 'client_address',
    'client_city', 'client_postcode', 'client_state_code', 'client_country_code',
    'issue_date', 'due_date', 'currency', 'exchange_rate', 'discount_percent',
    'discount_amount', 'shipping_fee', 'subtotal', 'tax_amount', 'total_amount',
    'payment_status', 'notes',
]
ITEM_FIELDS = ['description', 'classification_code', 'quantity', 'unit_price', 'tax_type', 'tax_rate', 'amount', 'tax_amount']


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA journal_mode=WAL')
    return con


def init_db():
    with connect() as con:
        con.executescript('''
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK(id=1),
                name TEXT DEFAULT '', email TEXT DEFAULT '', phone TEXT DEFAULT '',
                tin TEXT DEFAULT '', id_type TEXT DEFAULT 'BRN', id_number TEXT DEFAULT '',
                msic TEXT DEFAULT '', activity TEXT DEFAULT '', sst_number TEXT DEFAULT '',
                address TEXT DEFAULT '', city TEXT DEFAULT '', postcode TEXT DEFAULT '',
                state_code TEXT DEFAULT '', country_code TEXT DEFAULT 'MYS'
            );
            INSERT OR IGNORE INTO profile(id) VALUES (1);
            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY,
                invoice_number TEXT NOT NULL UNIQUE,
                client_name TEXT NOT NULL,
                client_tin TEXT DEFAULT '', client_id_type TEXT DEFAULT 'BRN',
                client_id_number TEXT DEFAULT '', client_email TEXT DEFAULT '',
                client_phone TEXT DEFAULT '', client_address TEXT DEFAULT '',
                client_city TEXT DEFAULT '', client_postcode TEXT DEFAULT '',
                client_state_code TEXT DEFAULT '', client_country_code TEXT DEFAULT 'MYS',
                issue_date TEXT NOT NULL, due_date TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'MYR', exchange_rate TEXT DEFAULT '1',
                discount_percent TEXT DEFAULT '0', discount_amount TEXT DEFAULT '0',
                shipping_fee TEXT DEFAULT '0', subtotal TEXT DEFAULT '0',
                tax_amount TEXT DEFAULT '0', total_amount TEXT DEFAULT '0',
                payment_status TEXT NOT NULL DEFAULT 'draft',
                lhdn_status TEXT NOT NULL DEFAULT 'NOT_SUBMITTED',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                description TEXT NOT NULL, classification_code TEXT NOT NULL,
                quantity TEXT NOT NULL, unit_price TEXT NOT NULL,
                tax_type TEXT NOT NULL, tax_rate TEXT NOT NULL,
                amount TEXT NOT NULL, tax_amount TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY, invoice_id TEXT REFERENCES invoices(id) ON DELETE SET NULL,
                original_name TEXT NOT NULL, stored_name TEXT NOT NULL,
                mime_type TEXT NOT NULL, source TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_invoice_created ON invoices(created_at);
            CREATE INDEX IF NOT EXISTS idx_attach_invoice ON attachments(invoice_id);
        ''')


def get_profile() -> dict:
    with connect() as con:
        return dict(con.execute('SELECT * FROM profile WHERE id=1').fetchone())


def save_profile(data: dict):
    values = [str(data.get(k) or '') for k in PROFILE_FIELDS]
    with connect() as con:
        con.execute('UPDATE profile SET ' + ','.join(f'{k}=?' for k in PROFILE_FIELDS) + ' WHERE id=1', values)


def suggest_invoice_number() -> str:
    """Preview a unique sequence; final uniqueness enforced by database."""
    prefix = f'INV-{datetime.now():%Y%m}-'
    with connect() as con:
        rows = con.execute('SELECT invoice_number FROM invoices WHERE invoice_number LIKE ?', (prefix + '%',)).fetchall()
    used = set()
    for r in rows:
        try:
            used.add(int(r['invoice_number'][len(prefix):]))
        except ValueError:
            pass
    candidate = 1
    while candidate in used:
        candidate += 1
    return f'{prefix}{candidate:04d}'


def save_invoice(data: dict, items: list[dict], invoice_id: str | None = None) -> str:
    """Atomic header + line item upsert; an existing invoice stays local-only."""
    if not items:
        raise ValueError('At least one invoice line item is required.')
    payload = [data.get(k, '') for k in INVOICE_FIELDS]
    with connect() as con:
        if invoice_id:
            existed = con.execute('SELECT 1 FROM invoices WHERE id=?', (invoice_id,)).fetchone()
            if not existed:
                raise ValueError('Invoice not found.')
            con.execute('UPDATE invoices SET ' + ','.join(f'{k}=?' for k in INVOICE_FIELDS) + ',updated_at=CURRENT_TIMESTAMP WHERE id=?', payload + [invoice_id])
            con.execute('DELETE FROM invoice_items WHERE invoice_id=?', (invoice_id,))
        else:
            invoice_id = str(uuid4())
            con.execute('INSERT INTO invoices (id,' + ','.join(INVOICE_FIELDS) + ') VALUES (' + ','.join('?' for _ in range(len(INVOICE_FIELDS) + 1)) + ')', [invoice_id] + payload)
        for item in items:
            con.execute('INSERT INTO invoice_items(invoice_id,' + ','.join(ITEM_FIELDS) + ') VALUES (' + ','.join('?' for _ in range(len(ITEM_FIELDS) + 1)) + ')', [invoice_id] + [str(item.get(k, '')) for k in ITEM_FIELDS])
    return invoice_id


def list_invoices() -> list[dict]:
    with connect() as con:
        result = con.execute('SELECT * FROM invoices ORDER BY issue_date DESC, created_at DESC').fetchall()
        return [dict(r) for r in result]


def get_invoice(invoice_id: str) -> tuple[dict, list[dict]] | None:
    with connect() as con:
        row = con.execute('SELECT * FROM invoices WHERE id=?', (invoice_id,)).fetchone()
        if not row:
            return None
        items = con.execute('SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id', (invoice_id,)).fetchall()
        return dict(row), [dict(r) for r in items]


def effective_status(invoice: dict, today: str | None = None) -> str:
    """Derive overdue without mutating stored payment state."""
    status = invoice['payment_status']
    if status == 'pending' and invoice['due_date'] < (today or datetime.now().date().isoformat()):
        return 'overdue'
    return status


def set_status(invoice_id: str, status: str):
    if status not in ('draft', 'pending', 'paid', 'cancelled'):
        raise ValueError('Unsupported payment status.')
    with connect() as con:
        con.execute('UPDATE invoices SET payment_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (status, invoice_id))


def delete_invoice(invoice_id: str):
    with connect() as con:
        con.execute('DELETE FROM invoices WHERE id=?', (invoice_id,))


def save_attachment(filename: str, content: bytes, mime: str, source: str, invoice_id: str | None = None) -> str:
    """Validate file signatures, cap size, store with random safe name."""
    if not content or len(content) > 10 * 1024 * 1024:
        raise ValueError('Upload a nonempty document up to 10 MB.')
    if content.startswith(b'\xff\xd8\xff'):
        extension, mime = '.jpg', 'image/jpeg'
    elif content.startswith(b'\x89PNG\r\n\x1a\n'):
        extension, mime = '.png', 'image/png'
    elif content.startswith(b'%PDF-'):
        extension, mime = '.pdf', 'application/pdf'
    else:
        raise ValueError('Only JPEG, PNG and PDF documents are accepted.')
    if source == 'camera' and not mime.startswith('image/'):
        raise ValueError('Camera captures must be images.')
    attachment_id = str(uuid4())
    stored_name = attachment_id + extension
    directory = DATA_DIR / 'uploads'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / stored_name
    target.write_bytes(content)
    try:
        with connect() as con:
            con.execute('''INSERT INTO attachments(id,invoice_id,original_name,stored_name,mime_type,source)
                VALUES(?,?,?,?,?,?)''', (attachment_id, invoice_id, str(filename)[:255], stored_name, mime, source))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return attachment_id


def list_attachments(invoice_id: str | None = None) -> list[dict]:
    with connect() as con:
        if invoice_id is None:
            result = con.execute('SELECT * FROM attachments ORDER BY created_at DESC').fetchall()
        else:
            result = con.execute('SELECT * FROM attachments WHERE invoice_id=? ORDER BY created_at DESC', (invoice_id,)).fetchall()
        return [dict(x) for x in result]


def attachment_bytes(attachment: dict) -> bytes:
    # Stored names are generated UUIDs; guard anyway before file access.
    name = attachment['stored_name']
    if Path(name).name != name:
        raise ValueError('Invalid attachment filename.')
    return (DATA_DIR / 'uploads' / name).read_bytes()


def delete_attachment(attachment_id: str):
    with connect() as con:
        item = con.execute('SELECT stored_name FROM attachments WHERE id=?', (attachment_id,)).fetchone()
        if item:
            con.execute('DELETE FROM attachments WHERE id=?', (attachment_id,))
    if item:
        (DATA_DIR / 'uploads' / item['stored_name']).unlink(missing_ok=True)


def save_business_logo(content: bytes) -> None:
    """Store a verified PNG/JPEG as a local optional business logo."""
    from io import BytesIO
    from PIL import Image
    if not content or len(content) > 2 * 1024 * 1024:
        raise ValueError('A business logo must be 2 MB or smaller.')
    try:
        with Image.open(BytesIO(content)) as im:
            if im.format not in ('PNG', 'JPEG'):
                raise ValueError('Logo must be JPEG or PNG.')
            im.verify()
    except (OSError, ValueError) as exc:
        raise ValueError('Please choose a valid PNG or JPEG image.') from exc
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitize/re-encode to consistent PNG format and strip embedded metadata.
    with Image.open(BytesIO(content)) as im:
        im.thumbnail((900, 900))
        im.convert('RGB').save(DATA_DIR / 'business-logo.png', format='PNG')


def get_business_logo() -> bytes | None:
    path = DATA_DIR / 'business-logo.png'
    return path.read_bytes() if path.exists() else None
