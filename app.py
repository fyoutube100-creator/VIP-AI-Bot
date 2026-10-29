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

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VIP_USERS = {
    "admin": "12345",
    "Fahim": "fahim",
    "vip1": "blackshoter",
    "boss": "gold99",
    "FARHAD": "Fm889896@",
    "trader_pro": "pro2026",
    "gold_king": "kingXAU",
    "fx_sniper": "sniper@123",
    "vip2": "pass2vip",
    "bull_master": "bullrun99",
    "bear_hunter": "hunter2026",
    "smart_money": "smc2026",
    "profit_maker": "profit#100",
    "signal_boss": "boss@2026",
    "alpha_trader": "alpha!fx",
    "pip_catcher": "catch100",
    "whale_alert": "whale999",
    "crypto_fx": "fx@crypto",
    "scalper_pro": "scalp50",
    "vip_trader": "tradeVIPx"
}

tv = TvDatafeed()
market_cache = {"time": 0, "spot": None, "eu": None}

def get_offset():
    try:
        if os.path.exists("offset.txt"):
            with open("offset.txt", "r") as f:
                return float(f.read().strip())
    except: pass
    return 0.0

def load_state():
    try:
        if os.path.exists('state.json'):
            with open('state.json', 'r') as f:
                data = json.load(f)
                if "active_trade_binary" not in data: data["active_trade_binary"] = None
                return data
    except: pass
    return {"active_trade_forex": None, "active_trade_binary": None, "trade_history": []}

def save_state(state):
    with open('state.json', 'w') as f:
        json.dump(state, f)

def load_devices():
    try:
        if os.path.exists('devices.json'):
            with open('devices.json', 'r') as f: return json.load(f)
    except: pass
    return {}

def save_devices(data):
    with open('devices.json', 'w') as f: json.dump(data, f)

def get_bd_time():
    # বাংলাদেশ সময় (UTC +6)
    return datetime.utcnow() + timedelta(hours=6)

@app.route('/')
def home(): return send_from_directory(BASE_DIR, 'login.html')

@app.route('/bot.html')
def bot_dashboard(): return send_from_directory(BASE_DIR, 'bot.html')

@app.route('/login.html')
def login_page(): return send_from_directory(BASE_DIR, 'login.html')

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
                approve_link = f"https://vip-ai-bot.onrender.com/api/approve/{device_id}"
                msg = f"🚨 *New Device Login Attempt!*\n\n👤 *User:* `{username}`\n📱 *Device:* `{device_name}`\n\n✅ *Approve below:*\n[👉 APPROVE DEVICE NOW]({approve_link})"
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
    active_trade_forex = state.get("active_trade_forex")
    active_trade_binary = state.get("active_trade_binary")
    trade_history = state.get("trade_history", [])
    
    forex_signal = {"asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "WAIT ⏳", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--", "status": "Analyzing...", "message": "উপযুক্ত এন্ট্রির জন্য অপেক্ষা করছে..."}
    binary_signal = {"asset": "EUR/USD", "type": "BINARY", "action": "WAIT ⏳", "timeframe": "-- : --", "status": "Analyzing...", "message": "মার্কেট স্ক্যান করা হচ্ছে..."}

    bd_now = get_bd_time()
    
    if bd_now.weekday() >= 5: 
        forex_signal.update({"action": "WEEKEND ⏸️", "status": "Market Offline", "message": "আজ উইকেন্ড! মার্কেট বন্ধ।"})
        binary_signal.update({"action": "WEEKEND ⏸️", "status": "Market Offline", "message": "আজ উইকেন্ড! OTC অফ।"})
        return jsonify({"forex": forex_signal, "binary": binary_signal, "history": trade_history[:10]})

    try:
        spot_data, eu_data = fetch_tradingview_data()
        
        # 🚀 Forex Logic (Unchanged)
        if spot_data is not None and not spot_data.empty and len(spot_data) >= 200:
            spot_data['EMA_20'] = ta.trend.ema_indicator(spot_data['close'].squeeze(), window=20)
            spot_data['EMA_50'] = ta.trend.ema_indicator(spot_data['close'].squeeze(), window=50)
            spot_data['EMA_200'] = ta.trend.ema_indicator(spot_data['close'].squeeze(), window=200)
            spot_data['RSI'] = ta.momentum.rsi(spot_data['close'].squeeze(), window=14)
            
            close = float(spot_data.iloc[-1]['close']) - get_offset()
            rsi, ema20, ema50, ema200 = float(spot_data.iloc[-1]['RSI']), float(spot_data.iloc[-1]['EMA_20']), float(spot_data.iloc[-1]['EMA_50']), float(spot_data.iloc[-1]['EMA_200'])
            
            if active_trade_forex:
                if active_trade_forex['action'] == 'BUY 🟢':
                    if close >= active_trade_forex['tp1_val']: active_trade_forex['result'] = 'WIN ✅'; trade_history.insert(0, active_trade_forex); active_trade_forex = None
                    elif close <= active_trade_forex['sl_val']: active_trade_forex['result'] = 'LOSS ❌'; trade_history.insert(0, active_trade_forex); active_trade_forex = None
                elif active_trade_forex['action'] == 'SELL 🔴':
                    if close <= active_trade_forex['tp1_val']: active_trade_forex['result'] = 'WIN ✅'; trade_history.insert(0, active_trade_forex); active_trade_forex = None
                    elif close >= active_trade_forex['sl_val']: active_trade_forex['result'] = 'LOSS ❌'; trade_history.insert(0, active_trade_forex); active_trade_forex = None

            if active_trade_forex is None:
                pip_55, pip_80 = 5.5, 8.0
                if close > ema200 and ema20 > ema50 and 50 < rsi < 70:
                    active_trade_forex = {"time": bd_now.strftime("%I:%M %p"), "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "BUY 🟢", "entry": close, "tp1_val": close + pip_55, "tp2_val": close + pip_80, "sl_val": close - pip_55, "result": "Running ⏳"}
                elif close < ema200 and ema20 < ema50 and 30 < rsi < 50:
                    active_trade_forex = {"time": bd_now.strftime("%I:%M %p"), "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "SELL 🔴", "entry": close, "tp1_val": close - pip_55, "tp2_val": close - pip_80, "sl_val": close + pip_55, "result": "Running ⏳"}

            if active_trade_forex:
                forex_signal.update({"action": active_trade_forex['action'], "entry": f"{active_trade_forex['entry']:.2f}", "tp1": f"{active_trade_forex['tp1_val']:.2f}", "tp2": f"{active_trade_forex['tp2_val']:.2f}", "sl": f"{active_trade_forex['sl_val']:.2f}", "status": "Running...", "message": "AI Confirmed: Trade is Currently Running."})
        
        # 🚀 Binary Setup (Advance Logic & Result Track)
        if eu_data is not None and not eu_data.empty and len(eu_data) >= 20:
            
            # Check Binary Result
            if active_trade_binary:
                try:
                    entry_dt = datetime.strptime(active_trade_binary['entry_time_full'], "%Y-%m-%d %H:%M:%S")
                    expiry_dt = datetime.strptime(active_trade_binary['expiry_time_full'], "%Y-%m-%d %H:%M:%S")
                    current_close = float(eu_data.iloc[-1]['close'])
                    
                    if bd_now >= entry_dt and active_trade_binary.get('entry_price') is None:
                        active_trade_binary['entry_price'] = current_close
                        active_trade_binary['status'] = "Running ⏳"
                        
                    elif bd_now >= expiry_dt and active_trade_binary.get('entry_price') is not None:
                        entry_p = active_trade_binary['entry_price']
                        is_call = 'CALL' in active_trade_binary['action']
                        
                        if is_call and current_close > entry_p: active_trade_binary['result'] = 'WIN ✅'
                        elif not is_call and current_close < entry_p: active_trade_binary['result'] = 'WIN ✅'
                        elif current_close == entry_p: active_trade_binary['result'] = 'REFUND 🔄'
                        else: active_trade_binary['result'] = 'LOSS ❌'
                            
                        active_trade_binary['entry'] = f"{entry_p:.5f}"
                        active_trade_binary['tp1_val'] = "1 Min Exp." 
                        active_trade_binary['sl_val'] = f"{current_close:.5f}"
                        
                        trade_history.insert(0, active_trade_binary)
                        active_trade_binary = None
                except Exception as e: print("Bin Result Error:", e); active_trade_binary = None
                    
            # Generate New Binary Signal
            if active_trade_binary is None:
                eu_data['RSI'] = ta.momentum.rsi(eu_data['close'].squeeze(), window=14)
                indicator_bb = ta.volatility.BollingerBands(close=eu_data['close'].squeeze(), window=20, window_dev=2)
                eu_data['BB_lower'] = indicator_bb.bollinger_lband()
                eu_data['BB_upper'] = indicator_bb.bollinger_hband()
                
                eu_close = float(eu_data.iloc[-1]['close'])
                eu_rsi = float(eu_data.iloc[-1]['RSI'])
                bb_low = float(eu_data.iloc[-1]['BB_lower'])
                bb_up = float(eu_data.iloc[-1]['BB_upper'])
                
                action = None
                if eu_rsi < 30 and eu_close <= bb_low: action = "CALL 🟢"
                elif eu_rsi > 70 and eu_close >= bb_up: action = "PUT 🔴"
                    
                if action:
                    entry_dt = bd_now + timedelta(minutes=1)
                    expiry_dt = bd_now + timedelta(minutes=2)
                    
                    active_trade_binary = {
                        "time": bd_now.strftime("%I:%M %p"),
                        "asset": "EUR/USD", "type": "BINARY", "action": action,
                        "entry_time_full": entry_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "expiry_time_full": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "time_display": f"{entry_dt.strftime('%H:%M')} - {expiry_dt.strftime('%H:%M')}",
                        "entry_price": None, "status": "Waiting for Entry ⏳", "result": "Pending"
                    }
            
            if active_trade_binary:
                binary_signal.update({
                    "action": active_trade_binary['action'],
                    "timeframe": active_trade_binary['time_display'],
                    "status": active_trade_binary['status'],
                    "message": "অ্যাডভান্স সিগন্যাল! এন্ট্রির জন্য প্রস্তুত হোন।" if active_trade_binary.get('entry_price') is None else "ট্রেড বর্তমানে রানিং..."
                })
    except Exception as e: print("System Error:", e)

    state.update({'active_trade_forex': active_trade_forex, 'active_trade_binary': active_trade_binary, 'trade_history': trade_history[:10]})
    save_state(state)
    return jsonify({"forex": forex_signal, "binary": binary_signal, "history": trade_history[:10]})

@app.route('/api/get_signal')
def get_signal(): return analyze_market()

if __name__ == '__main__': app.run(debug=True, port=5000)
