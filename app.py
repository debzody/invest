from flask import Flask, render_template, request, jsonify
import json
from datetime import datetime
import os
import logging
from dotenv import load_dotenv
import requests
import time

app = Flask(__name__)

# Load environment variables
load_dotenv()
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', 'cv67nshr01qi7f6oqp00cv67nshr01qi7f6oqp0g')  # Use provided Finnhub key

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = os.environ.get('DATA_FILE', 'investments.json')

# Scheme codes for mutual funds (update with actual mfapi.in codes)
SCHEME_CODES = {
    'HDFC_TECH': '152059',  # Example: HDFC Technology Fund - Direct Growth
    'INVESCO_TECH': '152863',  # Example: Invesco India Technology Fund (hypothetical)
    'MO_SMALLCAP': '152237',  # Example: Motilal Oswal Small Cap Fund (hypothetical)
    'MO_MULTICAP': '152651',  # Example: Motilal Oswal Multicap Fund (hypothetical)
    'MO_DEFENCE': '152712',  # Hypothetical - replace with real code
    'EDEL_TECH': '152438'  # Hypothetical - replace with real code
}

INITIAL_PRICES = {
    'SAP': 200.00, 'HONASA.NS': 450.00, 'HDFCLIFE': 620.00, 'JIOFIN': 350.00,
    'NTPCGREEN': 105.00, 'TATATECH': 1100.00, 'HDFC_TECH': 14.74,
    'INVESCO_TECH': 31.36, 'MO_SMALLCAP': 14.35, 'MO_MULTICAP': 10.00,
    'MO_DEFENCE': 6.72, 'EDEL_TECH': 15.82
}

CURRENCY = {
    'SAP': '$', 'HONASA.NS': '₹', 'HDFCLIFE': '₹', 'JIOFIN': '₹', 'NTPCGREEN': '₹',
    'TATATECH': '₹', 'HDFC_TECH': '₹', 'INVESCO_TECH': '₹', 'MO_SMALLCAP': '₹',
    'MO_MULTICAP': '₹', 'MO_DEFENCE': '₹', 'EDEL_TECH': '₹', 'INFY': '₹',
    'RELIANCE': '₹', 'TCS': '₹', 'HDFCBANK': '₹'
}

USD_TO_INR = 87.00

epf_value = 0  # Store EPF value globally

@app.route('/save_epf', methods=['POST'])
def save_epf():
    global epf_value
    data = request.json
    epf_value = data.get("epfAmount", 0)
    return jsonify({"status": "success", "epf": epf_value})

def load_investments():
    """Load existing investments from the data file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_investments():
    """Save investments to the data file."""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(investments, f, indent=4)
        logger.info(f"Saved investments to {DATA_FILE} at {datetime.now()}")
    except Exception as e:
        logger.error(f"Error saving investments at {datetime.now()}: {e}")

def get_nse_live_price(symbol):
    """Fetch live stock price from NSE India."""
    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com"
    }
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers)
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        price = data.get("priceInfo", {}).get("lastPrice")
        if price is not None:
            logger.info(f"Fetched NSE price for {symbol}: {price} at {datetime.now()}")
            return float(price)
        logger.warning(f"No valid price data for {symbol} from NSE at {datetime.now()}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch NSE price for {symbol}: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing NSE data for {symbol}: {e}")
        return None

def fetch_finnhub_price(symbol):
    """Fetch stock price from Finnhub for SAP SE."""
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        price = data.get("c")  # Current price
        if price is not None and price > 0:
            price = float(price)
            logger.info(f"Fetched {symbol} from Finnhub: {price} at {datetime.now()}")
            return price
        logger.warning(f"No valid price for {symbol} from Finnhub at {datetime.now()}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch {symbol} from Finnhub: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing Finnhub data for {symbol}: {e}")
        return None

def get_mutual_fund_nav(symbol):
    """Fetch latest NAV for a mutual fund using mfapi.in."""
    scheme_code = SCHEME_CODES.get(symbol)
    if not scheme_code:
        logger.warning(f"No scheme code found for {symbol} at {datetime.now()}")
        return None
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        nav_data = data["data"][0]  # Latest NAV entry
        latest_nav = float(nav_data["nav"])
        date = nav_data["date"]
        logger.info(f"Fetched NAV for {symbol} (code: {scheme_code}) from mfapi.in: {latest_nav} on {date} at {datetime.now()}")
        return latest_nav
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching NAV for {symbol} (code: {scheme_code}) from mfapi.in: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing NAV data for {symbol} (code: {scheme_code}) from mfapi.in: {e}")
        return None

def fetch_price(symbol):
    """Fetch price, prioritizing Finnhub for SAP SE, NSE for Indian stocks, and mfapi.in for mutual funds."""
    # Mutual funds
    if symbol in SCHEME_CODES:
        price = get_mutual_fund_nav(symbol)
        if price is not None:
            return price
        logger.info(f"No NAV from mfapi.in for {symbol}, using initial price if available")
        return None
    
    # SAP SE via Finnhub
    if symbol == 'SAP':
        price = fetch_finnhub_price(symbol)
        if price is not None:
            return price
        logger.info(f"No price from Finnhub for {symbol}, using initial price if available")
        return None
    
    # NSE stocks
    nse_symbol = symbol.replace('.NS', '') if '.NS' in symbol else symbol
    if nse_symbol in ['INFY', 'RELIANCE', 'TCS', 'HDFCBANK', 'HONASA', 'HDFCLIFE', 'JIOFIN', 'NTPCGREEN', 'TATATECH'] or '.NS' in symbol:
        price = get_nse_live_price(nse_symbol)
        if price is not None:
            return price
        logger.info(f"No price from NSE for {symbol}, using initial price if available")
    
    return None

def calculate_total_inr():
    total_inr = 0
    for inv in investments:
        value = inv['quantity'] * inv['current_price']
        if inv['currency'] == '$':  # SAP SE is in USD
            value *= USD_TO_INR
        total_inr += value
    return total_inr

# Load investments after all functions are defined
investments = load_investments()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_investment', methods=['POST'])
def add_investment():
    try:
        data = request.form
        symbol = data['symbol']
        investment = {
            'type': data['type'],
            'symbol': symbol,
            'name': data['name'],
            'quantity': float(data['quantity']),
            'purchase_price': float(data['purchase_price']),
            'current_price': float(data['purchase_price']),
            'currency': CURRENCY.get(symbol, '₹'),
            'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        if investment['type'] == 'stock':
            real_price = fetch_price(symbol)
            if real_price is not None:
                investment['current_price'] = real_price
            elif symbol in INITIAL_PRICES:
                investment['current_price'] = INITIAL_PRICES[symbol]
            else:
                return jsonify({'status': 'error', 'message': f'Could not fetch price for {symbol}'}), 400
        investments.append(investment)
        save_investments()
        return jsonify({'status': 'success'})
    except ValueError as e:
        logger.error(f"Validation error in add_investment: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid numeric input'}), 400
    except Exception as e:
        logger.error(f"Error in add_investment: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/add_investment/batch', methods=['POST'])
def add_investment_batch():
    try:
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({'status': 'error', 'message': 'Expected a list of investments'}), 400

        for investment_data in data:
            investment = {
                'type': investment_data.get('type', 'stock'),
                'symbol': investment_data['symbol'],
                'name': investment_data['name'],
                'quantity': float(investment_data.get('quantity', 1)),  # Default to 1
                'purchase_price': float(investment_data.get('purchase_price', 1)),  # Default to 1
                'current_price': float(investment_data.get('current_price', 1)),  # Default to 1
                'currency': CURRENCY.get(investment_data['symbol'], '₹'),
                'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            if investment['type'] == 'stock' and investment['symbol'] != 'SAP':  # Skip Finnhub for batch SAP
                real_price = fetch_price(investment['symbol'])
                if real_price is not None:
                    investment['current_price'] = real_price
                elif investment['symbol'] in INITIAL_PRICES:
                    investment['current_price'] = INITIAL_PRICES[investment['symbol']]
            investments.append(investment)
        
        save_investments()
        return jsonify({'status': 'success'})
    except ValueError as e:
        logger.error(f"Validation error in add_investment_batch: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid numeric input'}), 400
    except Exception as e:
        logger.error(f"Error in add_investment_batch: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_investments')
def get_investments():
    try:
        total_inr = calculate_total_inr()
        return jsonify({'investments': investments, 'total_inr': total_inr, "epf": epf_value})
    except Exception as e:
        logger.error(f"Error in get_investments: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/delete_investment', methods=['POST'])
def delete_investment():
    try:
        data = request.json
        index = data.get('index')
        index = int(index)
        if 0 <= index < len(investments):
            investments.pop(index)
            save_investments()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Invalid index'}), 400
    except (ValueError, TypeError):
        logger.error(f"Invalid index in delete_investment")
        return jsonify({'status': 'error', 'message': 'Index must be a number'}), 400
    except Exception as e:
        logger.error(f"Error in delete_investment: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/update_investment', methods=['POST'])
def update_investment():
    try:
        data = request.json
        index = data.get('index')
        index = int(index)
        if 0 <= index < len(investments):
            investments[index]['quantity'] = float(data['quantity'])
            investments[index]['purchase_price'] = float(data['purchase_price'])
            if 'current_price' in data and data['current_price'] is not None:
                investments[index]['current_price'] = float(data['current_price'])
            save_investments()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Invalid index'}), 400
    except (ValueError, TypeError):
        logger.error(f"Invalid data in update_investment")
        return jsonify({'status': 'error', 'message': 'Invalid input data'}), 400
    except Exception as e:
        logger.error(f"Error in update_investment: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/update_prices', methods=['GET'])
def trigger_update_prices():
    try:
        updated = False
        for inv in investments:
            if inv['type'] == 'stock':
                real_price = fetch_price(inv['symbol'])
                if real_price is not None:
                    inv['current_price'] = real_price
                    updated = True
                else:
                    logger.info(f"Retained last price for {inv['symbol']}: {inv['current_price']}")
                time.sleep(1)  # Avoid overwhelming servers
        if updated:
            save_investments()
        return jsonify({'status': 'Prices updated' if updated else 'No updates available'})
    except Exception as e:
        logger.error(f"Error in update_prices: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5002)))