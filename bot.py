import os
from datetime import datetime
import pytz
import gspread
import base64
import pyotp
from oauth2client.service_account import ServiceAccountCredentials
from SmartApi.smartConnect import SmartConnect

# ================== CONFIG FROM GITHUB SECRETS ==================

API_KEY = os.getenv("API_KEY")
CLIENT_CODE = os.getenv("CLIENT_CODE")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP_SECRET")
SHEET_URL = os.getenv("SHEET_URL")
GSHEET_CREDS_B64 = os.getenv("GSHEET_CREDS_B64")

DRY_RUN = True   # 🔴 keep TRUE until fully confident

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

    print(f"➡ {side} | Token={symbol_token} | Qty={qty}")

    if DRY_RUN:
        print("🧪 DRY RUN — order not placed")
        return "DRY_RUN"

    order = api.placeOrder({
        "variety": "NORMAL",
        "tradingsymbol": "",
        "symboltoken": symbol_token,
        "transactiontype": side,
        "exchange": "NSE",
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": qty
    })

    return "EXECUTED" if order else "FAILED"


def main():
    if not is_market_time():
        print("⏰ Outside market hours, exiting")
        return

    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).strftime("%d/%m/%Y")

    api = smartapi_login()
    sheet = setup_gsheet()
    rows = sheet.get_all_records()

    for i, row in enumerate(rows, start=2):
        row = {k.strip(): v for k, v in row.items()}

        if row.get("Date") != today:
            continue
        if row.get("Status"):
            continue
        if row.get("BUY/SELL") not in ["BUY", "SELL"]:
            continue

        result = place_order(api, row)
        sheet.update_cell(i, 7, result)  # Column G = Status

        print(f"✅ Row {i} → {result}")


if __name__ == "__main__":
    main()
