import os
import time
import datetime
import pytz
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

# ============== LOAD SECRETS ==============
API_KEY = os.getenv("API_KEY")
CLIENT_CODE = os.getenv("CLIENT_CODE")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP_SECRET")
SHEET_URL = os.getenv("SHEET_URL")
GSHEET_CREDS_B64 = os.getenv("GSHEET_CREDS_B64")

# ================== LOGIN ==================
def angel_login():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    api = SmartConnect(api_key=API_KEY)
    session = api.generateSession(CLIENT_CODE, PASSWORD, totp)

    if not session or not session.get("status"):
        raise Exception("Angel login failed")

    print("✅ Angel login successful")
    return api

# ================== SHEET ==================
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

# ================== ORDERS ==================
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

# ================== MAIN ==================
def run_bot():
    now = datetime.datetime.now(IST).time()
    if not (datetime.time(9, 15) <= now <= datetime.time(15, 0)):
        print("⏰ Outside market hours")
        return

    api = angel_login()
    sheet = connect_sheet()
    rows = sheet.get_all_records()

    today = datetime.date.today().strftime("%Y-%m-%d")

    for i, row in enumerate(rows, start=2):
        if row["Date"] != today:
            continue
        if row["Status"]:
            continue

        token = str(row["symbol token"])
        side = row["BUY/SELL"].upper()

        print(f"➡ ENTRY {side} | Token={token}")

        order_id = place_market(api, token, side)
        time.sleep(2)

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
