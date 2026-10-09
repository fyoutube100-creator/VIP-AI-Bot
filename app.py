from flask import Flask, jsonify, send_from_directory, request
import yfinance as yf
import ta
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🔒 VIP মেম্বারদের আইডি ও পাসওয়ার্ডের লিস্ট (আপনি চাইলে পরে আরও বাড়াতে পারবেন)
VIP_USERS = {
    "admin": "12345",
    "vip1": "blackshoter",
    "boss": "gold99",
    "FARHAD":"Fm889896@"
}

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/bot.html')
def bot_dashboard():
    return send_from_directory(BASE_DIR, 'bot.html')

@app.route('/login.html')
def login_page():
    return send_from_directory(BASE_DIR, 'login.html')

# 🔒 লগইন চেক করার সিকিউরিটি সিস্টেম
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
    try:
        gold_data = yf.download("GC=F", period="1d", interval="15m", progress=False)
        if not gold_data.empty:
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
            
            if ema20 > ema50 and 40 < rsi < 70:
                return {
                    "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "BUY 🟢",
                    "entry": f"{close:.2f}", "tp1": f"{close + (atr*1):.2f}", 
                    "tp2": f"{close + (atr*2):.2f}", "sl": f"{close - (atr*1.5):.2f}",
                    "status": "Signal Active", "message": "AI Confirmed: Strong Uptrend Detected."
                }
            elif ema20 < ema50 and 30 < rsi < 60:
                return {
                    "asset": "GOLD (XAUUSD)", "type": "FOREX", "action": "SELL 🔴",
                    "entry": f"{close:.2f}", "tp1": f"{close - (atr*1):.2f}", 
                    "tp2": f"{close - (atr*2):.2f}", "sl": f"{close + (atr*1.5):.2f}",
                    "status": "Signal Active", "message": "AI Confirmed: Strong Downtrend Detected."
                }

        eu_data = yf.download("EURUSD=X", period="1d", interval="1m", progress=False)
        if not eu_data.empty:
            eu_data['RSI'] = ta.momentum.rsi(eu_data['Close'].squeeze(), window=14)
            last_eu = eu_data.iloc[-1]
            eu_rsi = float(last_eu['RSI'])
            
            if eu_rsi < 30:
                return {
                    "asset": "EUR/USD", "type": "BINARY", "action": "UP 🟢",
                    "timeframe": "1 Minute", "payout": "80%+",
                    "status": "Signal Active", "message": "Oversold Zone! 1 Min Reversal Expected."
                }
            elif eu_rsi > 70:
                return {
                    "asset": "EUR/USD", "type": "BINARY", "action": "DOWN 🔴",
                    "timeframe": "1 Minute", "payout": "80%+",
                    "status": "Signal Active", "message": "Overbought Zone! 1 Min Reversal Expected."
                }

        return {
            "asset": "MARKET SCANNING...", "type": "WAITING", "action": "WAIT ⏳",
            "timeframe": "--", "payout": "--", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--",
            "status": "Analyzing...", "message": "মার্কেট ম্যাচ করেনি। এআই উপযুক্ত এন্ট্রির জন্য অপেক্ষা করছে..."
        }
    except Exception as e:
        return {
            "asset": "SCANNING...", "type": "WAITING", "action": "WAIT ⏳",
            "timeframe": "--", "payout": "--", "entry": "--", "tp1": "--", "tp2": "--", "sl": "--",
            "status": "Connecting...", "message": "লাইভ ডেটা ফেচ করা হচ্ছে, অপেক্ষা করুন..."
        }

@app.route('/api/get_signal')
def get_signal():
    return jsonify(analyze_market())

if __name__ == '__main__':
    app.run(debug=True, port=5000)
