from datetime import datetime, time
import pytz
import os
import time as t
import base64
import pyotp
import gspread

from SmartApi.smartConnect import SmartConnect
from oauth2client.service_account import ServiceAccountCredentials


# ===================== CONFIG =====================
IST = pytz.timezone("Asia/Kolkata")

TARGET_PCT = 0.01   # 1% target
SL_PCT = 0.01       # 1% stoploss
QTY = 1
EXCHANGE = "NSE"


# ===================== LOAD SECRETS =====================
API_KEY = os.getenv("API_KEY")
CLIENT_CODE = os.getenv("CLIENT_CODE")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP_SECRET")
SHEET_URL = os.getenv("SHEET_URL")
GSHEET_CREDS_B64 = os.getenv("GSHEET_CREDS_B64")


# ===================== LOGIN =====================
def angel_login():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    api = SmartConnect(api_key=API_KEY)

    session = api.generateSession(CLIENT_CODE, PASSWORD, totp)
    if not session or not session.get("status"):
        raise Exception("❌ Angel login failed")

    print("✅ Angel login successful")
    return api


# ===================== GOOGLE SHEET =====================
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


# ===================== ORDERS =====================
def place_market(api, token, side):
    order = api.placeOrder({
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
    return order


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


# ===================== AUTO SQUARE-OFF =====================
def auto_square_off(api):
    positions = api.position()

    if not positions or "data" not in positions:
        print("No open positions")
        return

    for pos in positions["data"]:
        net_qty = int(pos["netqty"])
        if net_qty != 0 and pos["producttype"] == "INTRADAY":
            exit_side = "SELL" if net_qty > 0 else "BUY"

            print(f"🔁 Squaring off {pos['tradingsymbol']} | Qty: {abs(net_qty)}")

            api.placeOrder({
                "variety": "NORMAL",
                "tradingsymbol": pos["tradingsymbol"],
                "symboltoken": pos["symboltoken"],
                "transactiontype": exit_side,
                "exchange": pos["exchange"],
                "ordertype": "MARKET",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": abs(net_qty)
            })


# ===================== MAIN BOT =====================
def run_bot():
    now = datetime.now(IST).time()

    # 🔴 AUTO SQUARE-OFF AT 3:00 PM
    if now >= time(15, 0):
        print("⏰ 3:00 PM reached — Auto square-off")
        api = angel_login()
        auto_square_off(api)
        return

    # NORMAL MARKET HOURS
    if not (time(9, 15) <= now < time(15, 0)):
        print("Outside market hours")
        return

    api = angel_login()
    sheet = connect_sheet()
    rows = sheet.get_all_records()

    today = datetime.now(IST).strftime("%Y-%m-%d")

    for i, row in enumerate(rows, start=2):
        if row["Date"] != today:
            continue

        if row.get("Status") == "EXECUTED":
            continue

        token = str(row["symbol token"])
        side = row["BUY/SELL"].upper()

        print(f"📥 ENTRY {side} | Token={token}")

        order_id = place_market(api, token, side)
        t.sleep(2)

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


# ===================== RUN =====================
if __name__ == "__main__":
    run_bot()
