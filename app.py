from flask import Flask, render_template, request, jsonify
import json
from datetime import datetime
import threading
import time
import yfinance as yf
import os

app = Flask(__name__)

DATA_FILE = 'investments.json'

def load_investments():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_investments():
    with open(DATA_FILE, 'w') as f:
        json.dump(investments, f, indent=4)

INITIAL_PRICES = {
    'SAP': 200.00, 'HONASA.NS': 450.00, 'HDFCLIFE': 620.00, 'JIOFIN': 350.00,
    'NTPCGREEN': 105.00, 'TATATECH': 1100.00, 'HDFC_TECH': 14.74,
    'INVESCO_TECH': 31.36, 'MO_SMALLCAP': 14.35, 'MO_MULTICAP': 10.00,
    'MO_DEFENCE': 6.72, 'EDEL_TECH': 15.82
}

CURRENCY = {
    'SAP': '€', 'HONASA.NS': '₹', 'HDFCLIFE': '₹', 'JIOFIN': '₹', 'NTPCGREEN': '₹',
    'TATATECH': '₹', 'HDFC_TECH': '₹', 'INVESCO_TECH': '₹', 'MO_SMALLCAP': '₹',
    'MO_MULTICAP': '₹', 'MO_DEFENCE': '₹', 'EDEL_TECH': '₹'
}

EUR_TO_INR = 90.00

def fetch_yahoo_price(symbol):
    try:
        ticker_symbol = 'SAP.DE' if symbol == 'SAP' else symbol
        stock = yf.Ticker(ticker_symbol)
        data = stock.history(period="1d")
        if not data.empty:
            price = float(data['Close'].iloc[-1])
            print(f"{datetime.now()} - Fetched {symbol} ({ticker_symbol}) daily: {price}")
            return price
        print(f"{datetime.now()} - No data for {symbol} ({ticker_symbol})")
        return None
    except Exception as e:
        print(f"{datetime.now()} - Error fetching {symbol} ({ticker_symbol}): {e}")
        return None

def calculate_total_inr():
    total_inr = 0
    for inv in investments:
        value = inv['quantity'] * inv['current_price']
        if inv['currency'] == '€':
            value *= EUR_TO_INR
        total_inr += value
    return total_inr

def update_prices():
    print(f"{datetime.now()} - Price update thread started")
    while True:
        for inv in investments:
            if inv['type'] == 'stock':
                real_price = fetch_yahoo_price(inv['symbol'])
                if real_price is not None:
                    inv['current_price'] = real_price
                else:
                    print(f"{datetime.now()} - Using last known price for {inv['symbol']}: {inv['current_price']}")
        save_investments()
        time.sleep(60)

investments = load_investments()
for inv in investments:
    if inv['type'] == 'stock':
        real_price = fetch_yahoo_price(inv['symbol'])
        if real_price is not None:
            inv['current_price'] = real_price
        else:
            print(f"{datetime.now()} - Startup fetch failed for {inv['symbol']}, using saved: {inv['current_price']}")
save_investments()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_investment', methods=['POST'])
def add_investment():
    data = request.form
    symbol = data['symbol']
    investment = {
        'type': data['type'],
        'symbol': symbol,
        'name': data['name'],
        'quantity': float(data['quantity']),
        'purchase_price': float(data['purchase_price']),
        'current_price': float(data['purchase_price']),
        'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'currency': CURRENCY.get(symbol, '₹')
    }
    if investment['type'] == 'stock':
        real_price = fetch_yahoo_price(symbol)
        if real_price is not None:
            investment['current_price'] = real_price
    investments.append(investment)
    save_investments()
    return jsonify({'status': 'success'})

@app.route('/get_investments')
def get_investments():
    total_inr = calculate_total_inr()
    return jsonify({'investments': investments, 'total_inr': total_inr})

@app.route('/delete_investment', methods=['POST'])
def delete_investment():
    data = request.json
    index = data.get('index')
    try:
        index = int(index)
        if 0 <= index < len(investments):
            investments.pop(index)
            save_investments()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Invalid index'})
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Index must be a number'})

@app.route('/update_investment', methods=['POST'])
def update_investment():
    data = request.json
    index = data.get('index')
    try:
        index = int(index)
        if 0 <= index < len(investments):
            investments[index]['quantity'] = float(data['quantity'])
            investments[index]['purchase_price'] = float(data['purchase_price'])
            if data['current_price'] is not None:
                investments[index]['current_price'] = float(data['current_price'])
            save_investments()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Invalid index'})
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Index must be a number'})

if __name__ == '__main__':
    price_thread = threading.Thread(target=update_prices, daemon=True)
    price_thread.start()
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)