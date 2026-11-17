from flask import Flask, jsonify, send_from_directory, request
from tvDatafeed import TvDatafeed, Interval
import ta
import pandas as pd
import os
import traceback
from datetime import datetime, timedelta
import urllib.request
import json
import time
import threading

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VIP_USERS = {
    "admin": "12345", "Fahim": "fahim", "vip1": "blackshoter", "boss": "gold99",
    "FARHAD": "Fm889896@", "trader_pro": "pro2026", "gold_king": "kingXAU",
    "fx_sniper": "sniper@123", "vip2": "pass2vip", "bull_master": "bullrun99",
    "bear_hunter": "hunter2026", "smart_money": "smc2026", "profit_maker": "profit#100",
    "signal_boss": "boss@2026", "alpha_trader": "alpha!fx", "pip_catcher": "catch100",
    "whale_alert": "whale999", "crypto_fx": "fx@crypto", "scalper_pro": "scalp50",
    "r": "t"
}

tv = TvDatafeed()
market_cache = {"time": 0, "spot": None, "eu": None}

def get_bd_time(): return datetime.utcnow() + timedelta(hours=6)

def load_json_file(filename, default_data):
    filepath = os.path.join(BASE_DIR, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f: return json.load(f)
        except: pass
    return default_data

def save_json_file(filename, data):
    filepath = os.path.join(BASE_DIR, filename)
    with open(filepath, 'w') as f: json.dump(data, f, indent=4)

def load_users_data(): return load_json_file('users_data.json', {})
def save_users_data(data): save_json_file('users_data.json', data)
def load_devices(): return load_json_file('devices.json', {})
def save_devices(data): save_json_file('devices.json', data)
def load_state():
    data = load_json_file('state.json', {"active_trade_forex": None, "active_trade_binary": None, "trade_history": []})
    if "active_trade_binary" not in data: data["active_trade_binary"] = None
    return data
def save_state(state): save_json_file('state.json', state)

def send_telegram_alert(msg):
    botToken = os.environ.get('TELEGRAM_BOT_TOKEN')
    chatId = "7204862590"
    if botToken:
        try:
            url = f"https://api.telegram.org/bot{botToken}/sendMessage"
            req = urllib.request.Request(url, data=json.dumps({'chat_id': chatId, 'text': msg, 'parse_mode': 'Markdown'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req)
        except Exception as e: print("Telegram Alert Error:", e)

def daily_profit_updater():
    while True:
        now = get_bd_time()
        if now.hour == 0 and now.minute == 1:
            users = load_users_data()
            updated = False
            for username, data in users.items():
                deposit = float(data.get('deposit', 0.0))
                if deposit > 0:
                    daily_profit = deposit * 0.50 
                    current_balance = float(data.get('balance', 0.0))
                    current_total_profit = float(data.get('total_profit', 0.0))
                    
                    data['profit'] = f"{daily_profit:.2f}"
                    data['balance'] = f"{(current_balance + daily_profit):.2f}"
                    data['total_profit'] = f"{(current_total_profit + daily_profit):.2f}"
                    data['last_profit_update'] = now.strftime("%Y-%m-%d")
                    updated = True
            if updated:
                save_users_data(users)
                send_telegram_alert("🤖 *AI SYSTEM ALERT*\n\n✅ Daily 50% profit has been automatically distributed to all active accounts!")
            time.sleep(60) 
        time.sleep(30)

threading.Thread(target=daily_profit_updater, daemon=True).start()

last_update_id = 0
def telegram_polling():
    global last_update_id
    botToken = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not botToken: return
    while True:
        try:
            url = f"https://api.telegram.org/bot{botToken}/getUpdates?offset={last_update_id + 1}&timeout=10"
            response = urllib.request.urlopen(urllib.request.Request(url), timeout=15)
            data = json.loads(response.read().decode('utf-8'))
            
            for result in data.get('result', []):
                last_update_id = result['update_id']
                message = result.get('message', {})
                chat_id = str(message.get('chat', {}).get('id', ''))
                text = message.get('text', '')
                
                if chat_id == "7204862590":
                    if text.startswith('/set '):
                        parts = text.split()
                        if len(parts) >= 4:
                            _, username, field, value = parts[0], parts[1], parts[2].lower(), " ".join(parts[3:])
                            valid_fields = ['balance', 'deposit', 'profit', 'total_profit', 'withdraw']
                            if field in valid_fields:
                                users = load_users_data()
                                if username not in users: users[username] = {"balance": "0.00", "deposit": "0.00", "profit": "0.00", "total_profit": "0.00", "withdraw": "0.00"}
                                if field == 'deposit':
                                    try:
                                        dep_amount = float(value)
                                        daily_profit = dep_amount * 0.50
                                        new_balance = dep_amount + daily_profit
                                        users[username]['deposit'] = f"{dep_amount:.2f}"
                                        users[username]['profit'] = f"{daily_profit:.2f}"
                                        users[username]['balance'] = f"{new_balance:.2f}"
                                        current_total_profit = float(users[username].get('total_profit', "0.00"))
                                        users[username]['total_profit'] = f"{current_total_profit + daily_profit:.2f}"
                                        save_users_data(users)
                                        send_telegram_alert(f"🤖 *AI Setup Done!*\n👤 *User:* `{username}`\n📥 *Deposit:* ${dep_amount:.2f}\n📈 *Daily Profit (50%):* ${daily_profit:.2f}\n💵 *New Balance:* ${new_balance:.2f}")
                                    except ValueError: send_telegram_alert("❌ *Error:* Deposit amount must be a number!")
                                else:
                                    users[username][field] = value
                                    save_users_data(users)
                                    send_telegram_alert(f"✅ *Data Updated!*\n👤 *User:* `{username}`\n📝 *Field:* {field}\n💰 *New Value:* ${value}")
                            else: send_telegram_alert(f"❌ *Invalid Field!*\nUse: `balance`, `deposit`, `profit`, `total_profit`, `withdraw`")
                    
                    # 🚀 নতুন: এক্টিভ ইউজার দেখার কমান্ড
                    elif text == '/users':
                        devices = load_devices()
                        active_users = set()
                        for dev in devices.values():
                            if dev.get('status') == 'approved': active_users.add(dev.get('username'))
                        
                        if active_users:
                            msg = "🟢 *Active Logged-in Users:*\n\n"
                            for i, u in enumerate(active_users, 1):
                                msg += f"{i}. 👤 `{u}`  ➔  🔑 `{VIP_USERS.get(u, 'Removed from code')}`\n"
                            send_telegram_alert(msg)
                        else: send_telegram_alert("🔴 *No active users found.*")

                    # 🚀 নতুন: ইউজার কিক-আউট করার কমান্ড
                    elif text.startswith('/logout '):
                        parts = text.split()
                        if len(parts) >= 2:
                            target = parts[1]
                            devices = load_devices()
                            updated = False
                            for d_id in list(devices.keys()):
                                if devices[d_id].get('username') == target:
                                    del devices[d_id]
                                    updated = True
                            if updated:
                                save_devices(devices)
                                send_telegram_alert(f"✅ *Success!*\nUser `{target}` has been forcibly logged out.")
                            else: send_telegram_alert(f"❌ User `{target}` is not currently logged in.")
        except Exception as e: pass
        time.sleep(3)

threading.Thread(target=telegram_polling, daemon=True).start()

@app.route('/')
def home(): return send_from_directory(BASE_DIR, 'login.html')
@app.route('/bot.html')
def bot_dashboard(): return send_from_directory(BASE_DIR, 'bot.html')
@app.route('/login.html')
def login_page(): return send_from_directory(BASE_DIR, 'login.html')
@app.route('/ai_account.html')
def ai_account_page(): return send_from_directory(BASE_DIR, 'ai_account.html')

@app.route('/api/login', methods=['POST'])
def login_api():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    device_id = data.get('device_id')
    device_name = data.get('device_name', 'Unknown Device')

    if username in VIP_USERS and VIP_USERS[username] == password:
        devices = load_devices()
        if device_id in devices and devices[device_id]['status'] == 'approved' and devices[device_id]['username'] == username:
            return jsonify({"status": "success"})
        if device_id not in devices or devices[device_id]['status'] != 'pending':
            devices[device_id] = {'username': username, 'device_name': device_name, 'status': 'pending', 'time': get_bd_time().strftime("%Y-%m-%d %I:%M %p")}
            save_devices(devices)
            botToken = os.environ.get('TELEGRAM_BOT_TOKEN')
            if botToken:
                msg = f"🚨 *New Device Login Attempt!*\n\n👤 *User:* `{username}`\n📱 *Device:* `{device_name}`\n\n✅ *Approve below:*\n[👉 APPROVE DEVICE NOW](https://vip-ai-bot.onrender.com/api/approve/{device_id})"
                try: urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{botToken}/sendMessage", data=json.dumps({'chat_id': "7204862590", 'text': msg, 'parse_mode': 'Markdown'}).encode('utf-8'), headers={'Content-Type': 'application/json'}))
                except: pass
        return jsonify({"status": "pending", "message": "আপনার ডিভাইসটি এডমিনের এপ্রুভালের জন্য অপেক্ষমান রয়েছে।"})
    return jsonify({"status": "error", "message": "ভুল আইডি বা পাসওয়ার্ড!"})

@app.route('/api/approve/<device_id>')
def approve_device(device_id):
    devices = load_devices()
    if device_id in devices:
        devices[device_id]['status'] = 'approved'
        save_devices(devices)
        return f"<div style='text-align: center; margin-top: 50px;'><h1 style='color: green;'>✅ Approved!</h1><h2>User: {devices[device_id]['username']}</h2></div>"
    return "<h1 style='color: red; text-align: center;'>❌ Invalid!</h1>"

# 🚀 নতুন: Strict Session Auth Checker
@app.route('/api/check_auth', methods=['POST'])
def check_auth():
    username = request.get_json().get('username', '')
    if not username or username not in VIP_USERS:
        return jsonify({"status": "unauthorized"})
    devices = load_devices()
    if not any(d.get('username') == username and d.get('status') == 'approved' for d in devices.values()):
        return jsonify({"status": "unauthorized"})
    return jsonify({"status": "success"})

@app.route('/api/sync_price', methods=['POST'])
def sync_price():
    try:
        tv_price = float(request.get_json().get('tv_price'))
        spot = tv.get_hist(symbol='XAUUSD', exchange='OANDA', interval=Interval.in_1_minute, n_bars=10)
        if spot is not None and not spot.empty:
            with open("offset.txt", "w") as f: f.write(str(float(spot['close'].iloc[-1]) - tv_price))
            return jsonify({"status": "success", "message": "Synced!"})
        return jsonify({"status": "error", "message": "Failed."})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/submit_form', methods=['POST'])
def submit_form():
    try:
        send_telegram_alert(request.get_json().get('message', 'No message provided.'))
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/withdraw', methods=['POST'])
def api_withdraw():
    try:
        data = request.get_json()
        username, method, wallet, amount = data.get('username'), data.get('method'), data.get('wallet'), float(data.get('amount', 0))
        if not username or amount < 10: return jsonify({"status": "error", "message": "Invalid request."})
        users = load_users_data()
        if username not in users: users[username] = {"balance": "0.00", "deposit": "0.00", "profit": "0.00", "total_profit": "0.00", "withdraw": "0.00"}
        current_balance, current_withdraw = float(users[username].get('balance', "0.00")), float(users[username].get('withdraw', "0.00"))
        if current_balance < amount: return jsonify({"status": "error", "message": "Insufficient balance! Your balance is lower than requested amount."})
        users[username]['balance'] = f"{(current_balance - amount):.2f}"
        users[username]['withdraw'] = f"{(current_withdraw + amount):.2f}"
        save_users_data(users)
        send_telegram_alert(f"💸 *NEW WITHDRAWAL REQUEST*\n\n👤 *User:* `{username}`\n🏦 *Method:* {method}\n💳 *Wallet/ID:* `{wallet}`\n💰 *Amount:* ${amount:.2f}\n📉 *Remaining Balance:* ${float(users[username]['balance']):.2f}")
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/get_user_data', methods=['POST'])
def get_user_data():
    try:
        username = request.get_json().get('username', '')
        users = load_users_data()
        if username in users: return jsonify({"status": "success", "data": users[username]})
        return jsonify({"status": "success", "data": {"balance": "0.00", "deposit": "0.00", "profit": "0.00", "total_profit": "0.00", "withdraw": "0.00"}})
    except Exception as e: return jsonify({"status": "error"})

def fetch_tradingview_data():
    global market_cache
    if time.time() - market_cache["time"] < 60 and market_cache["spot"] is not None: return market_cache["spot"], market_cache["eu"]
    try:
        spot = tv.get_hist(symbol='XAUUSD', exchange='OANDA', interval=Interval.in_1_minute, n_bars=250)
        eu = tv.get_hist(symbol='EURUSD', exchange='OANDA', interval=Interval.in_1_minute, n_bars=100)
        market_cache.update({"time": time.time(), "spot": spot, "eu": eu})
        return spot, eu
    except: return market_cache["spot"], market_cache["eu"]

def analyze_market():
    state = load_state()
    active_trade_forex, active_trade_binary, trade_history = state.get("active_trade_forex"), state.get("active_trade_binary"), state.get("trade_history", [])
    forex_signal = {"asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "WAIT ⏳", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--", "status": "Analyzing...", "message": "উপযুক্ত এন্ট্রির জন্য অপেক্ষা করছে..."}
    binary_signal = {"asset": "EUR/USD", "type": "BINARY", "action": "WAIT ⏳", "timeframe": "-- : --", "status": "Analyzing...", "message": "মার্কেট স্ক্যান করা হচ্ছে..."}
    bd_now = get_bd_time()
    if bd_now.weekday() >= 5: 
        forex_signal.update({"action": "WEEKEND ⏸️", "status": "Market Offline", "message": "আজ উইকেন্ড! মার্কেট বন্ধ।"})
        binary_signal.update({"action": "WEEKEND ⏸️", "status": "Market Offline", "message": "আজ উইকেন্ড! OTC অফ।"})
        return jsonify({"forex": forex_signal, "binary": binary_signal, "history": trade_history[:10]})

    try:
        spot_data, eu_data = fetch_tradingview_data()
        forex_closed_now = False 
        if spot_data is not None and not spot_data.empty and len(spot_data) >= 200:
            spot_data['EMA_20'] = ta.trend.ema_indicator(spot_data['close'].squeeze(), window=20); spot_data['EMA_50'] = ta.trend.ema_indicator(spot_data['close'].squeeze(), window=50); spot_data['EMA_200'] = ta.trend.ema_indicator(spot_data['close'].squeeze(), window=200); spot_data['RSI'] = ta.momentum.rsi(spot_data['close'].squeeze(), window=14)
            close = float(spot_data.iloc[-1]['close'])
            rsi, ema20, ema50, ema200 = float(spot_data.iloc[-1]['RSI']), float(spot_data.iloc[-1]['EMA_20']), float(spot_data.iloc[-1]['EMA_50']), float(spot_data.iloc[-1]['EMA_200'])
            
            if active_trade_forex:
                if active_trade_forex['action'] == 'BUY 🟢':
                    if close >= active_trade_forex['tp1_val']: 
                        active_trade_forex['result'] = 'WIN ✅'; send_telegram_alert(f"✅ *FOREX RESULT: WIN*\n📈 *Asset:* GOLD\n🎯 *Action:* BUY")
                        trade_history.insert(0, active_trade_forex); active_trade_forex = None; forex_closed_now = True
                    elif close <= active_trade_forex['sl_val']: 
                        active_trade_forex['result'] = 'LOSS ❌'; send_telegram_alert(f"❌ *FOREX RESULT: LOSS*\n📈 *Asset:* GOLD\n🎯 *Action:* BUY")
                        trade_history.insert(0, active_trade_forex); active_trade_forex = None; forex_closed_now = True
                elif active_trade_forex['action'] == 'SELL 🔴':
                    if close <= active_trade_forex['tp1_val']: 
                        active_trade_forex['result'] = 'WIN ✅'; send_telegram_alert(f"✅ *FOREX RESULT: WIN*\n📈 *Asset:* GOLD\n🎯 *Action:* SELL")
                        trade_history.insert(0, active_trade_forex); active_trade_forex = None; forex_closed_now = True
                    elif close >= active_trade_forex['sl_val']: 
                        active_trade_forex['result'] = 'LOSS ❌'; send_telegram_alert(f"❌ *FOREX RESULT: LOSS*\n📈 *Asset:* GOLD\n🎯 *Action:* SELL")
                        trade_history.insert(0, active_trade_forex); active_trade_forex = None; forex_closed_now = True

            if active_trade_forex is None and not forex_closed_now:
                pip_55, pip_80 = 5.5, 8.0
                if close > ema20 and ema20 > ema50 and ema50 > ema200 and 55 < rsi < 75:
                    active_trade_forex = {"time": bd_now.strftime("%I:%M %p"), "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "BUY 🟢", "entry": close, "tp1_val": close + pip_55, "tp2_val": close + pip_80, "sl_val": close - pip_55, "result": "Running ⏳"}
                    send_telegram_alert(f"🚨 *NEW FOREX SIGNAL*\n📈 *Asset:* GOLD\n🟢 *Action:* BUY\n🎯 *Entry:* {close:.2f}")
                elif close < ema20 and ema20 < ema50 and ema50 < ema200 and 25 < rsi < 45:
                    active_trade_forex = {"time": bd_now.strftime("%I:%M %p"), "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "SELL 🔴", "entry": close, "tp1_val": close - pip_55, "tp2_val": close - pip_80, "sl_val": close + pip_55, "result": "Running ⏳"}
                    send_telegram_alert(f"🚨 *NEW FOREX SIGNAL*\n📈 *Asset:* GOLD\n🔴 *Action:* SELL\n🎯 *Entry:* {close:.2f}")

            if active_trade_forex: forex_signal.update({"action": active_trade_forex['action'], "entry": f"{active_trade_forex['entry']:.2f}", "tp1": f"{active_trade_forex['tp1_val']:.2f}", "tp2": f"{active_trade_forex['tp2_val']:.2f}", "sl": f"{active_trade_forex['sl_val']:.2f}", "status": "Running...", "message": "AI Confirmed: Trade is Currently Running."})
        
        binary_closed_now = False 
        if eu_data is not None and not eu_data.empty and len(eu_data) >= 20:
            if active_trade_binary:
                try:
                    entry_dt = datetime.strptime(active_trade_binary['entry_time_full'], "%Y-%m-%d %H:%M:%S")
                    expiry_dt = datetime.strptime(active_trade_binary['expiry_time_full'], "%Y-%m-%d %H:%M:%S")
                    current_close = float(eu_data.iloc[-1]['close'])
                    if bd_now >= entry_dt and active_trade_binary.get('entry_price') is None:
                        active_trade_binary['entry_price'] = current_close; active_trade_binary['status'] = "Running ⏳"
                    elif bd_now >= expiry_dt and active_trade_binary.get('entry_price') is not None:
                        entry_p = active_trade_binary['entry_price']
                        is_call = 'CALL' in active_trade_binary['action']
                        if is_call and current_close > entry_p: active_trade_binary['result'] = 'WIN ✅'
                        elif not is_call and current_close < entry_p: active_trade_binary['result'] = 'WIN ✅'
                        elif current_close == entry_p: active_trade_binary['result'] = 'REFUND 🔄'
                        else: active_trade_binary['result'] = 'LOSS ❌'
                        active_trade_binary['entry'] = f"{entry_p:.5f}"; active_trade_binary['tp1_val'] = "1 Min Exp."; active_trade_binary['sl_val'] = f"{current_close:.5f}"
                        send_telegram_alert(f"🏁 *BINARY RESULT: {active_trade_binary['result']}*\n📉 *Asset:* EUR/USD")
                        trade_history.insert(0, active_trade_binary); active_trade_binary = None; binary_closed_now = True
                except Exception as e: active_trade_binary = None
                    
            if active_trade_binary is None and not binary_closed_now:
                eu_data['RSI'] = ta.momentum.rsi(eu_data['close'].squeeze(), window=14)
                indicator_bb = ta.volatility.BollingerBands(close=eu_data['close'].squeeze(), window=20, window_dev=2)
                eu_data['BB_lower'] = indicator_bb.bollinger_lband(); eu_data['BB_upper'] = indicator_bb.bollinger_hband()
                eu_close, eu_rsi, bb_low, bb_up = float(eu_data.iloc[-1]['close']), float(eu_data.iloc[-1]['RSI']), float(eu_data.iloc[-1]['BB_lower']), float(eu_data.iloc[-1]['BB_upper'])
                action = None
                if eu_rsi < 25 and eu_close <= bb_low: action = "CALL 🟢"
                elif eu_rsi > 75 and eu_close >= bb_up: action = "PUT 🔴"
                if action:
                    entry_dt = bd_now + timedelta(minutes=1); expiry_dt = bd_now + timedelta(minutes=2)
                    active_trade_binary = {"time": bd_now.strftime("%I:%M %p"), "asset": "EUR/USD", "type": "BINARY", "action": action, "entry_time_full": entry_dt.strftime("%Y-%m-%d %H:%M:%S"), "expiry_time_full": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"), "time_display": f"{entry_dt.strftime('%H:%M')} - {expiry_dt.strftime('%H:%M')}", "entry_price": None, "status": "Waiting for Entry ⏳", "result": "Pending"}
                    send_telegram_alert(f"🚨 *NEW BINARY SIGNAL*\n📉 *Asset:* EUR/USD\n🔵 *Action:* {action}")
            
            if active_trade_binary: binary_signal.update({"action": active_trade_binary['action'], "timeframe": active_trade_binary['time_display'], "status": active_trade_binary['status'], "message": "অ্যাডভান্স সিগন্যাল! এন্ট্রির জন্য প্রস্তুত হোন।" if active_trade_binary.get('entry_price') is None else "ট্রেড বর্তমানে রানিং..."})
    except Exception as e: pass

    state.update({'active_trade_forex': active_trade_forex, 'active_trade_binary': active_trade_binary, 'trade_history': trade_history[:10]})
    save_state(state)
    return jsonify({"forex": forex_signal, "binary": binary_signal, "history": trade_history[:10]})

@app.route('/api/get_signal')
def get_signal(): return analyze_market()

if __name__ == '__main__': app.run(debug=True, host="0.0.0.0", port=5000)
