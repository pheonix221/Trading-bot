# ================== IMPORTS ==================
from datetime import datetime, time, date
import pytz
import sys
import os
import time as time_module
import pyotp
import base64
import gspread

from SmartApi.smartConnect import SmartConnect
from oauth2client.service_account import ServiceAccountCredentials

# ================== CONFIG ==================
IST = pytz.timezone("Asia/Kolkata")

TARGET_PCT = 0.01     # 1%
SL_PCT = 0.01         # 1%
QTY = 1

EXCHANGE = "NSE"

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
SQUARE_OFF_TIME = time(15, 0)   # 🔴 3:00 PM auto square-off

# ================== LOAD SECRETS ==================
API_KEY = os.getenv("API_KEY")
CLIENT_CODE = os.getenv("CLIENT_CODE")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = "23HF32I3BXUB74NY6PZNLC7F3I"
SHEET_URL = os.getenv("SHEET_URL")
GSHEET_CREDS_B64 = os.getenv("GSHEET_CREDS_B64")

# ================== LOGIN ==================
def angel_login():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    api = SmartConnect(api_key=API_KEY)
    session = api.generateSession(CLIENT_CODE, PASSWORD, totp)

    if not session or not session.get("status"):
        raise Exception("❌ Angel login failed")

    print("✅ Angel login successful")
    return api

# ================== GOOGLE SHEET ==================
def connect_sheet():
    creds_json = base64.b64decode(GSHEET_CREDS_B64).decode("utf-8")
    with open("credentials.json", "w") as f:
        f.write(creds_json)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )
    client = gspread.authorize(creds)
    return client.open_by_url(SHEET_URL).sheet1

# ================== ORDER FUNCTIONS ==================
def place_market(api, token, side):
    return api.placeOrder({
        "variety": "NORMAL",
        "tradingsymbol": "",
        "symboltoken": token,
        "transactiontype": side,
        "exchange": EXCHANGE,
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": QTY
    })

def place_sl(api, token, side, sl_price):
    exit_side = "SELL" if side == "BUY" else "BUY"

    api.placeOrder({
        "variety": "STOPLOSS",
        "tradingsymbol": "",
        "symboltoken": token,
        "transactiontype": exit_side,
        "exchange": EXCHANGE,
        "ordertype": "STOPLOSS_MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": QTY,
        "triggerprice": round(sl_price, 1)
    })

def place_target(api, token, side, target_price):
    exit_side = "SELL" if side == "BUY" else "BUY"

    api.placeOrder({
        "variety": "NORMAL",
        "tradingsymbol": "",
        "symboltoken": token,
        "transactiontype": exit_side,
        "exchange": EXCHANGE,
        "ordertype": "LIMIT",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": QTY,
        "price": round(target_price, 1)
    })

# ================== AUTO SQUARE-OFF ==================
def auto_square_off(api):
    print("🔔 Running AUTO SQUARE-OFF")

    positions = api.position()["data"] or []

    for pos in positions:
        qty = int(pos["netqty"])
        if qty == 0:
            continue

        side = "SELL" if qty > 0 else "BUY"

        print(f"🔄 Squaring off {pos['tradingsymbol']} | Qty={abs(qty)}")

        api.placeOrder({
            "variety": "NORMAL",
            "tradingsymbol": pos["tradingsymbol"],
            "symboltoken": pos["symboltoken"],
            "transactiontype": side,
            "exchange": pos["exchange"],
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "quantity": abs(qty)
        })

# ================== MAIN BOT ==================
def run_bot():
    now_time = datetime.now(IST).time()
    today = date.today().strftime("%Y-%m-%d")

    print("⏰ Current IST Time:", now_time)

    api = angel_login()

    # 🔴 AUTO SQUARE-OFF CHECK
    if now_time >= SQUARE_OFF_TIME:
        auto_square_off(api)
        return

    # ⛔ Market time validation
    if not (MARKET_OPEN <= now_time <= MARKET_CLOSE):
        print("⏰ Outside market hours")
        return

    sheet = connect_sheet()
    rows = sheet.get_all_records()

    for i, row in enumerate(rows, start=2):
        if row["Date"] != today:
            continue
        if row.get("Status"):
            continue

        token = str(row["symbol token"])
        side = row["BUY/SELL"].upper()

        print(f"➡ ENTRY {side} | Token={token}")

        order_id = place_market(api, token, side)
        time_module.sleep(2)

        trades = api.tradeBook()["data"]
        trade = next(t for t in trades if t["orderid"] == order_id)
        entry = float(trade["averageprice"])

        if side == "BUY":
            sl_price = entry * (1 - SL_PCT)
            target_price = entry * (1 + TARGET_PCT)
        else:
            sl_price = entry * (1 + SL_PCT)
            target_price = entry * (1 - TARGET_PCT)

        place_sl(api, token, side, sl_price)
        place_target(api, token, side, target_price)

        sheet.update_cell(i, 5, "EXECUTED")

        print(
            f"✅ ENTRY={entry:.2f} | "
            f"SL={sl_price:.2f} | "
            f"TARGET={target_price:.2f}"
        )

# ================== RUN ==================
if __name__ == "__main__":
    run_bot()


