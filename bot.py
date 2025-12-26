

# ===================== DRY RUN TRADING BOT =====================
# This version DOES NOT place real orders
# It only prints order parameters to verify order capability
# ===============================================================

from SmartApi.smartConnect import SmartConnect
from datetime import datetime, time
import pytz
import os

# ===================== CONFIG =====================
DRY_RUN = True           # 🔴 KEEP True for testing
EXCHANGE = "NSE"
QTY = 1

# Test stock (cheap & liquid)
SYMBOL_TOKEN = "3045"    # IDEA
SIDE = "BUY"

# ===================== TIME CHECK (IST) =====================
ist = pytz.timezone("Asia/Kolkata")
now = datetime.now(ist).time()

market_open = time(9, 15)
market_close = time(15, 30)

print("Current IST Time:", now)

if not (market_open <= now <= market_close):
    print("Outside market hours")
    exit()

print("Market hours OK")

# ===================== LOGIN =====================
api_key = os.environ.get("API_KEY")
client_id = os.environ.get("CLIENT_ID")
password = os.environ.get("PASSWORD")
totp = os.environ.get("TOTP")

smartapi = SmartConnect(api_key)
session = smartapi.generateSession(client_id, password, totp)

if not session.get("status"):
    print("Login failed:", session)
    exit()

print("Login successful")

# ===================== ORDER FUNCTIONS =====================
def place_market(api, token, side):
    order_params = {
        "variety": "NORMAL",
        "tradingsymbol": "",
        "symboltoken": token,
        "transactiontype": side,
        "exchange": EXCHANGE,
        "ordertype": "MARKET",
        "producttype": "INTRADAY",
        "duration": "DAY",
        "quantity": QTY
    }

    print("MARKET ORDER PARAMS:", order_params)

    if DRY_RUN:
        print("DRY RUN: Market order would be placed here")
        return None
    else:
        res = api.placeOrder(order_params)
        print("ORDER RESPONSE:", res)
        return res


def place_sl(api, token, side, sl_price):
    exit_side = "SELL" if side == "BUY" else "BUY"

    sl_params = {
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
    }

    print("SL ORDER PARAMS:", sl_params)

    if DRY_RUN:
        print("DRY RUN: SL order would be placed here")
        return None
    else:
        res = api.placeOrder(sl_params)
        print("SL RESPONSE:", res)
        return res


# ===================== EXECUTION =====================
print("Starting trade logic")

place_market(smartapi, SYMBOL_TOKEN, SIDE)

# dummy SL price just for test
place_sl(smartapi, SYMBOL_TOKEN, SIDE, sl_price=6.5)

print("Bot execution finished")
