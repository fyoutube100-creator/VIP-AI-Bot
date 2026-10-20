from flask import Flask, jsonify, send_from_directory, request
import yfinance as yf
import ta
import os
import traceback
from datetime import datetime
import urllib.request
import json
import time
import requests

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🔒 VIP মেম্বারদের আইডি ও পাসওয়ার্ড
VIP_USERS = {
    "admin": "12345",
    "vip1": "blackshoter",
    "boss": "gold99",
    "FARHAD": "Fm889896@"
}

trade_history = []
active_trade_forex = None

# 🚀 API Caching System to prevent Yahoo Finance 429/401 bans
market_cache = {
    "time": 0,
    "spot": None,
    "future": None,
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
    global active_trade_forex
    try:
        data = request.get_json()
        tv_price = float(data.get('tv_price'))
        
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        
        spot_data = yf.Ticker("XAUUSD=X", session=session).history(period="1d", interval="1m")
        if spot_data.empty:
            spot_data = yf.Ticker("GC=F", session=session).history(period="1d", interval="1m")
            
        if not spot_data.empty:
            yf_price = float(spot_data['Close'].iloc[-1])
            offset = yf_price - tv_price
            
            with open("offset.txt", "w") as f:
                f.write(str(offset))
                
            active_trade_forex = None
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

def fetch_yahoo_data():
    global market_cache
    current_time = time.time()
    
    # 💡 60 সেকেন্ড ক্যাশিং (Yahoo এর ব্যান এড়াতে)
    if current_time - market_cache["time"] < 60 and market_cache["spot"] is not None:
        return market_cache["spot"], market_cache["future"], market_cache["eu"]
        
    try:
        session = requests.Session()
        # ব্রাউজার স্পুফিং
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "*/*"
        })
        
        spot = yf.Ticker("XAUUSD=X", session=session).history(period="5d", interval="1m")
        future = yf.Ticker("GC=F", session=session).history(period="5d", interval="1m")
        eu = yf.Ticker("EURUSD=X", session=session).history(period="5d", interval="1m")
        
        market_cache["time"] = current_time
        market_cache["spot"] = spot
        market_cache["future"] = future
        market_cache["eu"] = eu
        
        return spot, future, eu
    except Exception as e:
        print("YF Fetch Error:", e)
        return market_cache["spot"], market_cache["future"], market_cache["eu"]

def analyze_market():
    global active_trade_forex, trade_history
    
    forex_signal = {"asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "WAIT ⏳", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--", "status": "Analyzing...", "message": "উপযুক্ত এন্ট্রির জন্য অপেক্ষা করছে..."}
    binary_signal = {"asset": "EUR/USD", "type": "BINARY", "action": "WAIT ⏳", "timeframe": "--", "payout": "--", "status": "Analyzing...", "message": "মার্কেট স্ক্যান করা হচ্ছে..."}

    current_day = datetime.now().weekday()
    if current_day >= 5: 
        forex_signal.update({"action": "WEEKEND ⏸️", "status": "Market Offline", "message": "আজ উইকেন্ড! ফরেক্স মার্কেট বন্ধ রয়েছে।"})
        binary_signal.update({"action": "WEEKEND ⏸️", "status": "Market Offline", "message": "আজ উইকেন্ড! OTC অফ।"})
        return {"forex": forex_signal, "binary": binary_signal, "history": trade_history[:10]}

    try:
        spot_data, future_data, eu_data = fetch_yahoo_data()
        
        df = None
        if spot_data is not None and not spot_data.empty and len(spot_data) >= 50:
            df = spot_data
        elif future_data is not None and not future_data.empty and len(future_data) >= 50:
            df = future_data
            
        if df is not None:
            df['EMA_20'] = ta.trend.ema_indicator(df['Close'].squeeze(), window=20)
            df['EMA_50'] = ta.trend.ema_indicator(df['Close'].squeeze(), window=50)
            df['RSI'] = ta.momentum.rsi(df['Close'].squeeze(), window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'].squeeze(), df['Low'].squeeze(), df['Close'].squeeze(), window=14)
            
            last_candle = df.iloc[-1]
            raw_close = float(last_candle['Close'])
            
            offset = get_offset()
            close = raw_close - offset
            
            rsi = float(last_candle['RSI'])
            ema20 = float(last_candle['EMA_20'])
            ema50 = float(last_candle['EMA_50'])
            atr = float(last_candle['ATR'])
            
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

            if active_trade_forex == None:
                if ema20 > ema50 and 40 < rsi < 70:
                    active_trade_forex = {
                        "time": datetime.now().strftime("%I:%M %p"),
                        "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "BUY 🟢",
                        "entry": close, "tp1_val": close + (atr * 3), "tp2_val": close + (atr * 5), "sl_val": close - (atr * 3),
                        "result": "Running ⏳"
                    }
                elif ema20 < ema50 and 30 < rsi < 60:
                    active_trade_forex = {
                        "time": datetime.now().strftime("%I:%M %p"),
                        "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "SELL 🔴",
                        "entry": close, "tp1_val": close - (atr * 3), "tp2_val": close - (atr * 5), "sl_val": close + (atr * 3),
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
            eu_data['RSI'] = ta.momentum.rsi(eu_data['Close'].squeeze(), window=14)
            last_eu = eu_data.iloc[-1]
            eu_rsi = float(last_eu['RSI'])
            if eu_rsi < 30:
                binary_signal.update({"action": "UP 🟢", "timeframe": "1 Minute", "payout": "80%+", "status": "Signal Active", "message": "Oversold Zone! 1 Min Reversal Expected."})
            elif eu_rsi > 70:
                binary_signal.update({"action": "DOWN 🔴", "timeframe": "1 Minute", "payout": "80%+", "status": "Signal Active", "message": "Overbought Zone! 1 Min Reversal Expected."})
    except Exception as e:
        print("Binary AI Error:", e)

    return jsonify({"forex": forex_signal, "binary": binary_signal, "history": trade_history[:10]})

@app.route('/api/get_signal')
def get_signal():
    return analyze_market()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
