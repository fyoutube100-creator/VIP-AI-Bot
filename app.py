from flask import Flask, jsonify, send_from_directory, request
import yfinance as yf
import ta
import os
import traceback
from datetime import datetime
import urllib.request
import json

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🔒 VIP মেম্বারদের আইডি ও পাসওয়ার্ড
VIP_USERS = {
    "Fahim": "irfa",
    "vip1": "blackshoter",
    "boss": "gold99",
    "FARD": "Fm6@"
}

trade_history = []
active_trade = None

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

def analyze_market():
    global active_trade, trade_history
    try:
        current_day = datetime.now().weekday()
        if current_day >= 5: 
            return {
                "asset": "MARKET CLOSED", "type": "WEEKEND", "action": "WEEKEND ⏸️",
                "timeframe": "--", "payout": "--", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--",
                "status": "Market Offline", "message": "আজ উইকেন্ড! ফরেক্স মার্কেট বন্ধ রয়েছে। সোমবার আবার সিগন্যাল শুরু হবে।",
                "history": trade_history[:10] if trade_history else []
            }

        # 🎯 স্পট এবং ফিউচার দুটোরই ডেটা নেওয়া হচ্ছে
        spot_data = yf.Ticker("XAUUSD=X").history(period="5d", interval="1m")
        future_data = yf.Ticker("GC=F").history(period="5d", interval="1m")
        
        # স্পট মার্কেটের একদম লাইভ রিয়েল প্রাইস বের করা হচ্ছে (TradingView এর সাথে ম্যাচ করার জন্য)
        actual_spot_price = None
        if not spot_data.empty:
            actual_spot_price = float(spot_data['Close'].iloc[-1])
        
        # এনালাইসিসের জন্য ইন্ডিকেটর ডেটা সেট করা
        df = None
        if not spot_data.empty and len(spot_data) >= 50:
            df = spot_data
        elif not future_data.empty and len(future_data) >= 50:
            df = future_data
            
        if df is not None:
            df['EMA_20'] = ta.trend.ema_indicator(df['Close'].squeeze(), window=20)
            df['EMA_50'] = ta.trend.ema_indicator(df['Close'].squeeze(), window=50)
            df['RSI'] = ta.momentum.rsi(df['Close'].squeeze(), window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'].squeeze(), df['Low'].squeeze(), df['Close'].squeeze(), window=14)
            
            last_candle = df.iloc[-1]
            
            # 💡 ম্যাজিক লজিক: ইন্ডিকেটর যেখান থেকেই আসুক, এন্ট্রি প্রাইস হবে সবসময় লাইভ স্পট প্রাইস!
            close = actual_spot_price if actual_spot_price else float(last_candle['Close'])
            
            rsi = float(last_candle['RSI'])
            ema20 = float(last_candle['EMA_20'])
            ema50 = float(last_candle['EMA_50'])
            atr = float(last_candle['ATR'])
            
            if active_trade and active_trade['asset'] == "GOLD (XAUUSD)":
                if active_trade['action'] == 'BUY 🟢':
                    if close >= active_trade['tp1_val']:
                        active_trade['result'] = 'WIN ✅'
                        trade_history.insert(0, active_trade)
                        active_trade = None
                    elif close <= active_trade['sl_val']:
                        active_trade['result'] = 'LOSS ❌'
                        trade_history.insert(0, active_trade)
                        active_trade = None
                elif active_trade['action'] == 'SELL 🔴':
                    if close <= active_trade['tp1_val']:
                        active_trade['result'] = 'WIN ✅'
                        trade_history.insert(0, active_trade)
                        active_trade = None
                    elif close >= active_trade['sl_val']:
                        active_trade['result'] = 'LOSS ❌'
                        trade_history.insert(0, active_trade)
                        active_trade = None

            if active_trade == None:
                if ema20 > ema50 and 40 < rsi < 70:
                    active_trade = {
                        "time": datetime.now().strftime("%I:%M %p"),
                        "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "BUY 🟢",
                        "entry": close, "tp1_val": close + (atr * 3), "tp2_val": close + (atr * 5), "sl_val": close - (atr * 3),
                        "result": "Running ⏳"
                    }
                elif ema20 < ema50 and 30 < rsi < 60:
                    active_trade = {
                        "time": datetime.now().strftime("%I:%M %p"),
                        "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "SELL 🔴",
                        "entry": close, "tp1_val": close - (atr * 3), "tp2_val": close - (atr * 5), "sl_val": close + (atr * 3),
                        "result": "Running ⏳"
                    }

        eu_ticker = yf.Ticker("EURUSD=X")
        eu_data = eu_ticker.history(period="5d", interval="1m")
        if not eu_data.empty and len(eu_data) >= 14 and active_trade == None:
            eu_data['RSI'] = ta.momentum.rsi(eu_data['Close'].squeeze(), window=14)
            last_eu = eu_data.iloc[-1]
            eu_rsi = float(last_eu['RSI'])
            if eu_rsi < 30:
                return {
                    "asset": "EUR/USD", "type": "BINARY", "action": "UP 🟢",
                    "timeframe": "1 Minute", "payout": "80%+",
                    "status": "Signal Active", "message": "Oversold Zone! 1 Min Reversal Expected.",
                    "history": trade_history[:10]
                }
            elif eu_rsi > 70:
                return {
                    "asset": "EUR/USD", "type": "BINARY", "action": "DOWN 🔴",
                    "timeframe": "1 Minute", "payout": "80%+",
                    "status": "Signal Active", "message": "Overbought Zone! 1 Min Reversal Expected.",
                    "history": trade_history[:10]
                }

        if active_trade:
            return {
                "asset": active_trade['asset'], "type": active_trade['type'], "action": active_trade['action'],
                "entry": f"{active_trade['entry']:.2f}", "tp1": f"{active_trade['tp1_val']:.2f}", 
                "tp2": f"{active_trade['tp2_val']:.2f}", "sl": f"{active_trade['sl_val']:.2f}",
                "status": "Running...", "message": "AI Confirmed: Trade is Currently Running.",
                "history": trade_history[:10]
            }

        return {
            "asset": "MARKET SCANNING...", "type": "WAITING", "action": "WAIT ⏳",
            "timeframe": "--", "payout": "--", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--",
            "status": "Analyzing...", "message": "মার্কেট ম্যাচ করেনি। এআই উপযুক্ত এন্ট্রির জন্য অপেক্ষা করছে...",
            "history": trade_history[:10]
        }
    except Exception as e:
        print("AI Error:", e)
        traceback.print_exc()
        return {
            "asset": "SCANNING...", "type": "WAITING", "action": "WAIT ⏳",
            "timeframe": "--", "payout": "--", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--",
            "status": "Connecting...", "message": "লাইভ ডেটা ফেচ করা হচ্ছে, অপেক্ষা করুন...",
            "history": trade_history[:10] if trade_history else []
        }

@app.route('/api/get_signal')
def get_signal():
    return jsonify(analyze_market())

if __name__ == '__main__':
    app.run(debug=True, port=5000)
