from flask import Flask, jsonify, send_from_directory, request
from tvDatafeed import TvDatafeed, Interval
import ta
import pandas as pd
import os
import traceback
from datetime import datetime
import urllib.request
import json
import time

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🔒 VIP মেম্বারদের আইডি ও পাসওয়ার্ড
VIP_USERS = {
    "Fahim": "fahim",
    "vip1": "blackshoter",
    "boss": "gold99",
    "FD": "F@"
}

# TradingView Datafeed
tv = TvDatafeed()

market_cache = {
    "time": 0,
    "spot": None,
    "eu": None
}

def get_offset():
    try:
        if os.path.exists("offset.txt"):
            with open("offset.txt", "r") as f:
                return float(f.read().strip())
    except:
        pass
    return 0.0

# 🚀 পারমানেন্ট ফাইল সেভ সিস্টেম 
def load_state():
    try:
        if os.path.exists('state.json'):
            with open('state.json', 'r') as f:
                return json.load(f)
    except:
        pass
    return {"active_trade_forex": None, "trade_history": []}

def save_state(state):
    with open('state.json', 'w') as f:
        json.dump(state, f)

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/bot.html')
def bot_dashboard():
    return send_from_directory(BASE_DIR, 'bot.html')

@app.route('/login.html')
def login_page():
    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/api/login', methods=['POST'])
def login_api():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if username in VIP_USERS and VIP_USERS[username] == password:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "ভুল আইডি বা পাসওয়ার্ড!"})

@app.route('/api/sync_price', methods=['POST'])
def sync_price():
    try:
        data = request.get_json()
        tv_price = float(data.get('tv_price'))
        
        spot_data = tv.get_hist(symbol='XAUUSD', exchange='OANDA', interval=Interval.in_1_minute, n_bars=10)
            
        if spot_data is not None and not spot_data.empty:
            tv_live_price = float(spot_data['close'].iloc[-1])
            offset = tv_live_price - tv_price
            
            with open("offset.txt", "w") as f:
                f.write(str(offset))
                
            return jsonify({"status": "success", "message": "Price Synced Successfully!"})
        else:
            return jsonify({"status": "error", "message": "Failed to fetch live data from Server."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/submit_form', methods=['POST'])
def submit_form():
    try:
        data = request.get_json()
        botToken = os.environ.get('TELEGRAM_BOT_TOKEN')
        chatId = "7204862590"
        message = data.get('message')
        
        if not botToken:
            return jsonify({"status": "error"})

        url = f"https://api.telegram.org/bot{botToken}/sendMessage"
        req = urllib.request.Request(
            url, 
            data=json.dumps({'chat_id': chatId, 'text': message, 'parse_mode': 'Markdown'}).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req)
        return jsonify({"status": "success"})
    except Exception as e:
        print("Telegram Error:", e)
        return jsonify({"status": "error"})

def fetch_tradingview_data():
    global market_cache
    current_time = time.time()
    
    if current_time - market_cache["time"] < 60 and market_cache["spot"] is not None:
        return market_cache["spot"], market_cache["eu"]
        
    try:
        spot = tv.get_hist(symbol='XAUUSD', exchange='OANDA', interval=Interval.in_1_minute, n_bars=100)
        eu = tv.get_hist(symbol='EURUSD', exchange='OANDA', interval=Interval.in_1_minute, n_bars=100)
        
        market_cache["time"] = current_time
        market_cache["spot"] = spot
        market_cache["eu"] = eu
        
        return spot, eu
    except Exception as e:
        return market_cache["spot"], market_cache["eu"]

def analyze_market():
    state = load_state()
    active_trade_forex = state.get("active_trade_forex")
    trade_history = state.get("trade_history", [])
    
    forex_signal = {"asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "WAIT ⏳", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--", "status": "Analyzing...", "message": "উপযুক্ত এন্ট্রির জন্য অপেক্ষা করছে..."}
    binary_signal = {"asset": "EUR/USD", "type": "BINARY", "action": "WAIT ⏳", "timeframe": "--", "payout": "--", "status": "Analyzing...", "message": "মার্কেট স্ক্যান করা হচ্ছে..."}

    current_day = datetime.now().weekday()
    if current_day >= 5: 
        forex_signal.update({"action": "WEEKEND ⏸️", "status": "Market Offline", "message": "আজ উইকেন্ড! ফরেক্স মার্কেট বন্ধ রয়েছে।"})
        binary_signal.update({"action": "WEEKEND ⏸️", "status": "Market Offline", "message": "আজ উইকেন্ড! OTC অফ।"})
        return jsonify({"forex": forex_signal, "binary": binary_signal, "history": trade_history[:10]})

    try:
        spot_data, eu_data = fetch_tradingview_data()
        
        if spot_data is not None and not spot_data.empty and len(spot_data) >= 50:
            spot_data['EMA_20'] = ta.trend.ema_indicator(spot_data['close'].squeeze(), window=20)
            spot_data['EMA_50'] = ta.trend.ema_indicator(spot_data['close'].squeeze(), window=50)
            spot_data['RSI'] = ta.momentum.rsi(spot_data['close'].squeeze(), window=14)
            spot_data['ATR'] = ta.volatility.average_true_range(spot_data['high'].squeeze(), spot_data['low'].squeeze(), spot_data['close'].squeeze(), window=14)
            
            last_candle = spot_data.iloc[-1]
            raw_close = float(last_candle['close'])
            
            close = raw_close - get_offset()
            
            rsi = float(last_candle['RSI'])
            ema20 = float(last_candle['EMA_20'])
            ema50 = float(last_candle['EMA_50'])
            atr = float(last_candle['ATR'])
            
            # 🎯 ফলাফল চেক করার লজিক
            if active_trade_forex:
                if active_trade_forex['action'] == 'BUY 🟢':
                    if close >= active_trade_forex['tp1_val']:
                        active_trade_forex['result'] = 'WIN ✅'
                        trade_history.insert(0, active_trade_forex)
                        active_trade_forex = None
                    elif close <= active_trade_forex['sl_val']:
                        active_trade_forex['result'] = 'LOSS ❌'
                        trade_history.insert(0, active_trade_forex)
                        active_trade_forex = None
                elif active_trade_forex['action'] == 'SELL 🔴':
                    if close <= active_trade_forex['tp1_val']:
                        active_trade_forex['result'] = 'WIN ✅'
                        trade_history.insert(0, active_trade_forex)
                        active_trade_forex = None
                    elif close >= active_trade_forex['sl_val']:
                        active_trade_forex['result'] = 'LOSS ❌'
                        trade_history.insert(0, active_trade_forex)
                        active_trade_forex = None

            # 🎯 নতুন সিগন্যাল জেনারেট লজিক (ATR ৪ গুণ এবং ৬ গুণ করা হয়েছে)
            if active_trade_forex is None:
                if ema20 > ema50 and 40 < rsi < 70:
                    active_trade_forex = {
                        "time": datetime.now().strftime("%I:%M %p"),
                        "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "BUY 🟢",
                        "entry": close, "tp1_val": close + (atr * 4.0), "tp2_val": close + (atr * 6.0), "sl_val": close - (atr * 4.0),
                        "result": "Running ⏳"
                    }
                elif ema20 < ema50 and 30 < rsi < 60:
                    active_trade_forex = {
                        "time": datetime.now().strftime("%I:%M %p"),
                        "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "SELL 🔴",
                        "entry": close, "tp1_val": close - (atr * 4.0), "tp2_val": close - (atr * 6.0), "sl_val": close + (atr * 4.0),
                        "result": "Running ⏳"
                    }

            if active_trade_forex:
                forex_signal.update({
                    "action": active_trade_forex['action'],
                    "entry": f"{active_trade_forex['entry']:.2f}", 
                    "tp1": f"{active_trade_forex['tp1_val']:.2f}", 
                    "tp2": f"{active_trade_forex['tp2_val']:.2f}", 
                    "sl": f"{active_trade_forex['sl_val']:.2f}",
                    "status": "Running...", 
                    "message": "AI Confirmed: Trade is Currently Running."
                })
    except Exception as e:
        print("Forex AI Error:", e)

    try:
        if eu_data is not None and not eu_data.empty and len(eu_data) >= 14:
            eu_data['RSI'] = ta.momentum.rsi(eu_data['close'].squeeze(), window=14)
            last_eu = eu_data.iloc[-1]
            eu_rsi = float(last_eu['RSI'])
            if eu_rsi < 30:
                binary_signal.update({"action": "UP 🟢", "timeframe": "1 Minute", "payout": "80%+", "status": "Signal Active", "message": "Oversold Zone! 1 Min Reversal Expected."})
            elif eu_rsi > 70:
                binary_signal.update({"action": "DOWN 🔴", "timeframe": "1 Minute", "payout": "80%+", "status": "Signal Active", "message": "Overbought Zone! 1 Min Reversal Expected."})
    except Exception as e:
        print("Binary AI Error:", e)

    # 💾 বর্তমান স্ট্যাটাস ফাইলে সেভ করা হচ্ছে
    state['active_trade_forex'] = active_trade_forex
    state['trade_history'] = trade_history[:10]
    save_state(state)

    return jsonify({"forex": forex_signal, "binary": binary_signal, "history": trade_history[:10]})

@app.route('/api/get_signal')
def get_signal():
    return analyze_market()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
