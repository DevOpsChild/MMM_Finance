import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import database as db

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
WEEKLY_BUDGET = float(os.getenv("WEEKLY_BUDGET", "140.0"))
WEEKLY_FREIZEIT_BUDGET = float(os.getenv("WEEKLY_FREIZEIT_BUDGET", "80.0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Telegram Bot Handler
# ---------------------------------------------------------------------------

def _check_user(update: Update) -> bool:
    """Nur autorisierter User darf den Bot steuern."""
    return update.effective_user.id == TELEGRAM_USER_ID


async def cmd_einkauf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /einkauf <betrag> <notiz> [kategorie]
    Beispiel: /einkauf 23,50 Rewe Lebensmittel
    """
    if not _check_user(update):
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Verwendung: /einkauf <betrag> <notiz> [kategorie]\n"
            "Beispiel: /einkauf 23,50 Rewe Lebensmittel"
        )
        return

    try:
        betrag = float(args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Betrag ungültig. Beispiel: 23,50 oder 23.50")
        return

    notiz = args[1]
    kategorie = args[2] if len(args) >= 3 else "Sonstiges"

    db.ensure_current_week(WEEKLY_BUDGET)
    db.add_einkauf(betrag, notiz, kategorie, WEEKLY_BUDGET, WEEKLY_FREIZEIT_BUDGET)

    row = db.get_current_week_budget()
    verbleibend = row["betrag"] - row["ausgegeben"]

    antwort = (
        f"✅ Einkauf gespeichert: {betrag:.2f}€ – {notiz} ({kategorie})\n"
        f"💰 Verbleibend diese Woche: {verbleibend:.2f}€"
    )
    if kategorie.lower() == "freizeit":
        fz = db.get_current_week_freizeit()
        fz_verbleibend = fz["betrag"] - fz["ausgegeben"]
        antwort += f"\n🎉 Freizeit verbleibend: {fz_verbleibend:.2f}€"

    await update.message.reply_text(antwort)


async def cmd_etf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /etf <betrag>
    Beispiel: /etf 12345,67
    """
    if not _check_user(update):
        return

    if not context.args:
        await update.message.reply_text("Verwendung: /etf <betrag>\nBeispiel: /etf 12345,67")
        return

    try:
        betrag = float(context.args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Betrag ungültig.")
        return

    db.update_vermoegen("etf", betrag)
    await update.message.reply_text(f"📈 ETF-Stand aktualisiert: {betrag:,.2f}€")


async def cmd_sparen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /sparen <betrag>
    Beispiel: /sparen 8000,00
    """
    if not _check_user(update):
        return

    if not context.args:
        await update.message.reply_text("Verwendung: /sparen <betrag>\nBeispiel: /sparen 8000,00")
        return

    try:
        betrag = float(context.args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Betrag ungültig.")
        return

    db.update_vermoegen("sparkonto", betrag)
    await update.message.reply_text(f"🏦 Sparkonto aktualisiert: {betrag:,.2f}€")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zeigt aktuelle Übersicht."""
    if not _check_user(update):
        return

    db.ensure_current_week(WEEKLY_BUDGET)
    db.ensure_current_week_freizeit(WEEKLY_FREIZEIT_BUDGET)
    row = db.get_current_week_budget()
    fz = db.get_current_week_freizeit()
    vermoegen = db.get_vermoegen()
    einkaeufe = db.get_letzte_einkaeufe(5)

    ausgegeben = row["ausgegeben"]
    verbleibend = row["betrag"] - ausgegeben
    fz_verbleibend = fz["betrag"] - fz["ausgegeben"]

    einkaeufe_text = "\n".join(
        f"  • {e['betrag']:.2f}€ – {e['notiz']} ({e['kategorie']})"
        for e in einkaeufe
    ) or "  Keine Einkäufe diese Woche"

    etf = vermoegen.get("etf", {}).get("betrag", 0)
    sparkonto = vermoegen.get("sparkonto", {}).get("betrag", 0)
    gesamt = etf + sparkonto

    await update.message.reply_text(
        f"📊 *Finanz-Übersicht*\n\n"
        f"🛒 *Wochenbudget*\n"
        f"  Budget:      {row['betrag']:.2f}€\n"
        f"  Ausgegeben:  {ausgegeben:.2f}€\n"
        f"  Verbleibend: {verbleibend:.2f}€\n\n"
        f"🎉 *Freizeitbudget*\n"
        f"  Budget:      {fz['betrag']:.2f}€\n"
        f"  Ausgegeben:  {fz['ausgegeben']:.2f}€\n"
        f"  Verbleibend: {fz_verbleibend:.2f}€\n\n"
        f"🧾 *Letzte Einkäufe*\n{einkaeufe_text}\n\n"
        f"💼 *Vermögen*\n"
        f"  ETF:         {etf:,.2f}€\n"
        f"  Sparkonto:   {sparkonto:,.2f}€\n"
        f"  Gesamt:      {gesamt:,.2f}€",
        parse_mode="Markdown"
    )


async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /budget <betrag> – setzt wöchentliches Budget neu
    """
    if not _check_user(update):
        return

    if not context.args:
        await update.message.reply_text("Verwendung: /budget <betrag>\nBeispiel: /budget 160")
        return

    try:
        betrag = float(context.args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Betrag ungültig.")
        return

    global WEEKLY_BUDGET
    WEEKLY_BUDGET = betrag
    await update.message.reply_text(f"✅ Wochenbudget auf {betrag:.2f}€ gesetzt.")


# ---------------------------------------------------------------------------
# API Endpoint
# ---------------------------------------------------------------------------

app_api = FastAPI(title="MMM-Finanzen API")

app_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app_api.get("/api/finanzen")
def get_finanzen():
    db.ensure_current_week(WEEKLY_BUDGET)
    db.ensure_current_week_freizeit(WEEKLY_FREIZEIT_BUDGET)
    row = db.get_current_week_budget()
    fz = db.get_current_week_freizeit()
    vermoegen = db.get_vermoegen()
    einkaeufe = db.get_letzte_einkaeufe(5)

    ausgegeben = row["ausgegeben"]
    verbleibend = row["betrag"] - ausgegeben
    prozent = round((ausgegeben / row["betrag"]) * 100) if row["betrag"] > 0 else 0

    fz_ausgegeben = fz["ausgegeben"]
    fz_verbleibend = fz["betrag"] - fz_ausgegeben
    fz_prozent = round((fz_ausgegeben / fz["betrag"]) * 100) if fz["betrag"] > 0 else 0

    etf = vermoegen.get("etf", {}).get("betrag", 0)
    sparkonto = vermoegen.get("sparkonto", {}).get("betrag", 0)

    return {
        "budget": {
            "gesamt": row["betrag"],
            "ausgegeben": round(ausgegeben, 2),
            "verbleibend": round(verbleibend, 2),
            "prozent_verbraucht": prozent,
            "woche": row["woche"],
        },
        "freizeit": {
            "gesamt": fz["betrag"],
            "ausgegeben": round(fz_ausgegeben, 2),
            "verbleibend": round(fz_verbleibend, 2),
            "prozent_verbraucht": fz_prozent,
        },
        "einkaeufe": einkaeufe,
        "vermoegen": {
            "etf": etf,
            "sparkonto": sparkonto,
            "gesamt": round(etf + sparkonto, 2),
            "etf_aktualisiert": vermoegen.get("etf", {}).get("aktualisiert_am", ""),
            "sparkonto_aktualisiert": vermoegen.get("sparkonto", {}).get("aktualisiert_am", ""),
        }
    }


# ---------------------------------------------------------------------------
# Lifespan: Telegram Bot + Scheduler starten
# ---------------------------------------------------------------------------

telegram_app: Application = None
scheduler = AsyncIOScheduler()


def weekly_reset():
    """Wird jeden Montag aufgerufen – ensure_current_week legt neue Woche an."""
    db.ensure_current_week(WEEKLY_BUDGET)
    logger.info("Wöchentlicher Budget-Reset durchgeführt.")


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    global telegram_app

    db.init_db()
    db.ensure_current_week(WEEKLY_BUDGET)
    db.ensure_current_week_freizeit(WEEKLY_FREIZEIT_BUDGET)

    # Telegram Bot initialisieren
    telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
    telegram_app.add_handler(CommandHandler("einkauf", cmd_einkauf))
    telegram_app.add_handler(CommandHandler("etf", cmd_etf))
    telegram_app.add_handler(CommandHandler("sparen", cmd_sparen))
    telegram_app.add_handler(CommandHandler("status", cmd_status))
    telegram_app.add_handler(CommandHandler("budget", cmd_budget))

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()

    # Scheduler: jeden Montag 00:01 neue Woche anlegen
    scheduler.add_job(weekly_reset, "cron", day_of_week="mon", hour=0, minute=1)
    scheduler.start()

    logger.info("Backend gestartet. Telegram-Bot läuft.")
    yield

    await telegram_app.updater.stop()
    await telegram_app.stop()
    await telegram_app.shutdown()
    scheduler.shutdown()


app_api.router.lifespan_context = lifespan


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app_api", host="0.0.0.0", port=8081, reload=False)
