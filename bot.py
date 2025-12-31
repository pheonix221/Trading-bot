from datetime import datetime, time
import pytz
import os
import time as t
import pyotp

from SmartApi.smartConnect import SmartConnect

# ===================== CONFIG =====================
IST = pytz.timezone("Asia/Kolkata")

TARGET_PCT = 0.01   # 1% target
SL_PCT = 0.01       # 1% stoploss
QTY = 1
EXCHANGE = "NSE"


# ===================== LOAD SECRETS =====================
API_KEY = ("RZFN84ry")
CLIENT_CODE = ("AAAA624603")
PASSWORD = ("8320")
TOTP_SECRET = ("23HF32I3BXUB74NY6PZNLC7F3I")

# ===================== LOGIN =====================
def angel_login():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    api = SmartConnect(api_key=API_KEY)

    session = api.generateSession(CLIENT_CODE, PASSWORD, totp)
    if not session or not session.get("status"):
        raise Exception("❌ Angel login failed")

    print("✅ Angel login successful")
    return api


# ===================== ORDERS =====================
def place_market(api, symbol, token, side, qty):
    order = api.placeOrder({
        "variety": "NORMAL",
        "tradingsymbol": symbol,
        "symboltoken": token,
        "transactiontype": side,
        "exchange": EXCHANGE,
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": qty
    })

    print("🧾 ENTRY ORDER RESPONSE:", order)

    if not order or order.get("status") != True:
        print("❌ Entry order rejected")
        return None

    return order


def place_sl(api, symbol, token, side, sl_price, qty):
    exit_side = "SELL" if side == "BUY" else "BUY"
    api.placeOrder({
        "variety": "STOPLOSS",
        "tradingsymbol": symbol,      # ✅ FIXED
        "symboltoken": token,
        "transactiontype": exit_side,
        "exchange": EXCHANGE,
        "ordertype": "STOPLOSS_MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": qty,              # ✅ FIXED
        "triggerprice": round(sl_price, 1)
    })


def place_target(api, symbol, token, side, target_price, qty):
    exit_side = "SELL" if side == "BUY" else "BUY"
    api.placeOrder({
        "variety": "NORMAL",
        "tradingsymbol": symbol,      # ✅ FIXED
        "symboltoken": token,
        "transactiontype": exit_side,
        "exchange": EXCHANGE,
        "ordertype": "LIMIT",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": qty,              # ✅ FIXED
        "price": round(target_price, 1)
    })


# ===================== AUTO SQUARE-OFF =====================
def auto_square_off(api):
    try:
        positions = api.position()

        if not positions:
            print("ℹ️ No positions response")
            return

        data = positions.get("data")

        if not data:
            print("ℹ️ No open positions to square off")
            return

        for pos in data:
            qty = int(pos.get("netqty", 0))
            if qty == 0:
                continue

            side = "SELL" if qty > 0 else "BUY"

            print(f"🔁 Square-off {pos['tradingsymbol']} | Qty={abs(qty)}")

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

        print("✅ Auto square-off completed")

    except Exception as e:
        print(f"⚠️ Square-off error: {e}")

# ===================== MAIN BOT =====================
def run_bot():
    now = datetime.now(IST).time()

    if now >= time(15, 0):
        print("⏰ 3:00 PM reached — Auto square-off")
        api = angel_login()
        auto_square_off(api)
        return

    if not (time(9, 15) <= now < time(15, 0)):
        print("Outside market hours")
        return

    api = angel_login()
    rows = [
    {
        "Symbol": "IDEA-EQ",
        "Token": "14366",   
        "Side": "BUY",
        "Qty": 1
    }
    ]
    today = datetime.now(IST).strftime("%Y-%m-%d")

    for i, row in enumerate(rows, start=2):   # ✅ MOVED INSIDE
        if row["Date"] != today:
            continue

        if row.get("Status") == "EXECUTED":
            continue

        symbol = row["Symbol"]
        token = str(row["Token"])
        side = row["Side"]
        qty = int(row.get("Qty", QTY))

        order = place_market(api, symbol, token, side, qty)
        order_id = order.get("data", {}).get("orderid")

        trade = None
for _ in range(5):  # retry up to ~25 seconds
    t.sleep(5)
    trades = api.tradeBook().get("data", [])
    trade = next((x for x in trades if x["orderid"] == order_id), None)
    if trade:
        break   # ✅ break is INSIDE the loop

if not trade:
    print("❌ Trade not found yet, skipping SL/Target")
    continue   # ✅ continue is inside row loop

    entry = float(trade["averageprice"])

if side == "BUY":
    sl_price = entry * (1 - SL_PCT)
    target_price = entry * (1 + TARGET_PCT)
else:
    sl_price = entry * (1 + SL_PCT)
    target_price = entry * (1 - TARGET_PCT)
    

        place_sl(api, symbol, token, side, sl_price, qty)
        place_target(api, symbol, token, side, target_price, qty)
        

        print(
          f"ENTRY={entry:.2f} | "
          f"SL={sl_price:.2f} | "
          f"TARGET={target_price:.2f}"
        )

# ===================== RUN =====================
if __name__ == "__main__":
    run_bot()
