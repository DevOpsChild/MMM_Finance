import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "finanzen.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS wochen_budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            betrag REAL NOT NULL DEFAULT 160.0,
            ausgegeben REAL NOT NULL DEFAULT 0.0,
            woche TEXT NOT NULL,
            erstellt_am TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS einkaeufe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            betrag REAL NOT NULL,
            notiz TEXT,
            kategorie TEXT,
            datum TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vermoegen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            betrag REAL NOT NULL,
            aktualisiert_am TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Initiale ETF und Sparkonto Einträge falls noch nicht vorhanden
    for typ in ("etf", "sparkonto"):
        cur.execute("SELECT id FROM vermoegen WHERE typ = ?", (typ,))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO vermoegen (typ, betrag) VALUES (?, 0.0)", (typ,)
            )

    conn.commit()
    conn.close()


def get_current_week_budget():
    from datetime import date
    woche = date.today().strftime("%Y-W%W")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM wochen_budget WHERE woche = ? ORDER BY id DESC LIMIT 1",
        (woche,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def ensure_current_week(weekly_budget: float):
    """Legt Wochen-Eintrag an falls noch nicht vorhanden (Montags-Reset)."""
    from datetime import date
    woche = date.today().strftime("%Y-W%W")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM wochen_budget WHERE woche = ?", (woche,))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO wochen_budget (betrag, ausgegeben, woche) VALUES (?, 0.0, ?)",
            (weekly_budget, woche)
        )
        conn.commit()
    conn.close()


def add_einkauf(betrag: float, notiz: str, kategorie: str, weekly_budget: float):
    from datetime import date
    woche = date.today().strftime("%Y-W%W")
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO einkaeufe (betrag, notiz, kategorie) VALUES (?, ?, ?)",
        (betrag, notiz, kategorie)
    )
    cur.execute(
        "UPDATE wochen_budget SET ausgegeben = ausgegeben + ? WHERE woche = ?",
        (betrag, woche)
    )
    conn.commit()
    conn.close()


def update_vermoegen(typ: str, betrag: float):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE vermoegen SET betrag = ?, aktualisiert_am = datetime('now', 'localtime') WHERE typ = ?",
        (betrag, typ)
    )
    conn.commit()
    conn.close()


def get_letzte_einkaeufe(limit: int = 5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT betrag, notiz, kategorie, datum FROM einkaeufe ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vermoegen():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT typ, betrag, aktualisiert_am FROM vermoegen")
    rows = cur.fetchall()
    conn.close()
    return {r["typ"]: {"betrag": r["betrag"], "aktualisiert_am": r["aktualisiert_am"]} for r in rows}
