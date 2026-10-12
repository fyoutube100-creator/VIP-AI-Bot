from flask import Flask, jsonify, send_from_directory, request
import yfinance as yf
import ta
import os
import traceback
from datetime import datetime

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🔒 VIP মেম্বারদের আইডি ও পাসওয়ার্ড
VIP_USERS = {
    "admin": "12345",
    "vip1": "blackshoter",
    "boss": "gold99",
    "FARHAD": "Fm889896@"
}

# 📊 বটের হিস্ট্রি এবং লাইভ ট্রেড ট্র্যাকিং মেমরি
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

def analyze_market():
    global active_trade, trade_history
    try:
        gold_ticker = yf.Ticker("XAUUSD=X")
        gold_data = gold_ticker.history(period="5d", interval="1m")
        
        if not gold_data.empty and len(gold_data) >= 50:
            # ইন্ডিকেটরগুলো আগের মতোই ১০০% অপরিবর্তিত রাখা হয়েছে
            gold_data['EMA_20'] = ta.trend.ema_indicator(gold_data['Close'].squeeze(), window=20)
            gold_data['EMA_50'] = ta.trend.ema_indicator(gold_data['Close'].squeeze(), window=50)
            gold_data['RSI'] = ta.momentum.rsi(gold_data['Close'].squeeze(), window=14)
            gold_data['ATR'] = ta.volatility.average_true_range(gold_data['High'].squeeze(), gold_data['Low'].squeeze(), gold_data['Close'].squeeze(), window=14)
            
            last_gold = gold_data.iloc[-1]
            close = float(last_gold['Close'])
            rsi = float(last_gold['RSI'])
            ema20 = float(last_gold['EMA_20'])
            ema50 = float(last_gold['EMA_50'])
            atr = float(last_gold['ATR'])
            
            # 🔍 অটোমেটিক প্রফিট/লস চেক করা (ব্যাকগ্রাউন্ডে)
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

            # 🎯 নতুন সিগন্যাল খোঁজা (আপনার দেওয়া মূল লজিকে)
            if active_trade == None:
                if ema20 > ema50 and 40 < rsi < 70:
                    active_trade = {
                        "time": datetime.now().strftime("%I:%M %p"),
                        "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "BUY 🟢",
                        "entry": close, "tp1_val": close + (atr*1), 
                        "tp2_val": close + (atr*2), "sl_val": close - (atr*1.5),
                        "result": "Running ⏳"
                    }
                elif ema20 < ema50 and 30 < rsi < 60:
                    active_trade = {
                        "time": datetime.now().strftime("%I:%M %p"),
                        "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "SELL 🔴",
                        "entry": close, "tp1_val": close - (atr*1), 
                        "tp2_val": close - (atr*2), "sl_val": close + (atr*1.5),
                        "result": "Running ⏳"
                    }

        # বাইনারি লজিক (অপরিবর্তিত)
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

        # রেসপন্স তৈরি করা
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
