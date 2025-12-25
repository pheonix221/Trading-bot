import os
from datetime import datetime
import pytz
import gspread
import base64
import pyotp
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi.smartConnect import SmartConnect

# ================== CONFIG FROM GITHUB SECRETS ==================

API_KEY = os.getenv("RZFN84ry")
CLIENT_CODE = os.getenv("AAAA624603")
PASSWORD = os.getenv("8320")
TOTP_SECRET = os.getenv("TOTP_SECRET")
SHEET_URL = os.getenv("SHEET_URL")
GSHEET_CREDS_B64 = os.getenv("GSHEET_CREDS_B64")

DRY_RUN = False   # 🔴 keep TRUE until fully confident

# ================================================================


def is_market_time():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    return (now.hour == 9 and now.minute >= 15) or (9 < now.hour < 15)


def smartapi_login():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    obj = SmartConnect(api_key=API_KEY)
    session = obj.generateSession(CLIENT_CODE, PASSWORD, totp)

    if not session.get("status"):
        raise Exception("❌ SmartAPI login failed")

    print("✅ SmartAPI login successful")
    return obj


def setup_gsheet():
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
    sheet = client.open_by_url(SHEET_URL).sheet1
    return sheet


def place_order(api, row):
    symbol_token = row["symbol token"]
    side = row["BUY/SELL"].upper()
    qty = int(row["Quantity"])

    print(f"➡ {side} | Token={symbol)# ============================================================
# REAL INTRADAY TRADING BOT (GITHUB ACTIONS)
# Angel One SmartAPI + Google Sheets
# ============================================================

import os
import datetime
import pytz
import base64
import pyotp
import pandas as pd
from SmartApi.smartConnect import SmartConnect
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ============================================================
# 🔐 LOAD SECRETS
# ============================================================

SHEET_URL = os.getenv("SHEET_URL")
WORKSHEET_NAME = "Sheet1"

API_KEY = os.getenv("API_KEY")
CLIENT_CODE = os.getenv("CLIENT_CODE")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP_SECRET")
GSHEET_CREDS_B64 = os.getenv("GSHEET_CREDS_B64")

EXCHANGE = "NSE"
IST = pytz.timezone("Asia/Kolkata")

# 🔴 LIVE MODE
DRY_RUN = False   # ❗ REAL TRADING

# ============================================================
# ⏰ MARKET TIME CHECK
# ============================================================

def is_market_time():
    now = datetime.datetime.now(IST).time()
    return datetime.time(9, 15) <= now <= datetime.time(15, 0)

# ============================================================
# 🔐 ANGEL LOGIN
# ============================================================

def angel_login():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    angel = SmartConnect(api_key=API_KEY)
    session = angel.generateSession(CLIENT_CODE, PASSWORD, totp)

    if not session or not session.get("status"):
        raise Exception("❌ Angel login failed")

    print("✅ Angel login successful")
    return angel

# ============================================================
# 📊 GOOGLE SHEET CONNECT
# ============================================================

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
    return client.open_by_url(SHEET_URL).worksheet(WORKSHEET_NAME)

# ============================================================
# 📤 PLACE MARKET ORDER
# ============================================================

def place_market_order(angel, token, qty, side):
    print(f"➡ PLACING ORDER | {side} | Token={token} | Qty={qty}")

    order = angel.placeOrder({
        "variety": "NORMAL",
        "tradingsymbol": "",
        "symboltoken": token,
        "transactiontype": side,
        "exchange": EXCHANGE,
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": int(qty)
    })

    if not order:
        raise Exception("Order placement failed")

    return order

# ============================================================
# 🚀 MAIN RUN (SINGLE EXECUTION)
# ============================================================

def run_bot():
    if not is_market_time():
        print("⏰ Outside market hours, exiting")
        return

    angel = angel_login()
    sheet = connect_sheet()

    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    today = datetime.date.today().strftime("%Y-%m-%d")

    for i, row in df.iterrows():
        if str(row["Date"]) != today:
            continue

        if row["Status"]:
            continue

        token = str(row["Symbol Token"])
        qty = row["Quantity"]
        side = row["BUY / SELL"].upper()

        try:
            order_id = place_market_order(angel, token, qty, side)
            sheet.update_cell(i + 2, 7, "EXECUTED")
            print(f"✅ EXECUTED | Order ID: {order_id}")

        except Exception as e:
            sheet.update_cell(i + 2, 7, "FAILED")
            print("❌ FAILED:", e)

# ============================================================
# ▶️ ENTRY
# ============================================================

if __name__ == "__main__":
    run_bot()
