from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import numpy as np

app = Flask(__name__)
CORS(app)

def true_dcf(fcf, growth=0.05, discount=0.1, terminal=0.02, years=10):
    value = 0
    for i in range(1, years + 1):
        fcf *= (1 + growth)
        value += fcf / ((1 + discount) ** i)

    terminal_value = (fcf * (1 + terminal)) / (discount - terminal)
    value += terminal_value / ((1 + discount) ** years)
    return value

def ai_risk(volatility, valuation_gap, drawdown):
    score = volatility * 40 + valuation_gap * 30 + drawdown * 30
    return min(100, round(score))
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
API_KEY = os.getenv("FMP_API_KEY")

@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    # Fetch cash flow
    cf_url = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{ticker}?limit=5&apikey={API_KEY}"
    r = requests.get(cf_url).json()

    if not r or "freeCashFlow" not in r[0]:
        return jsonify({"error": "No cash flow data"}), 404

    fcf = [year["freeCashFlow"] for year in r if year["freeCashFlow"]]

    # DCF assumptions
    discount_rate = 0.10
    terminal_growth = 0.025

    value = 0
    for i, cash in enumerate(fcf):
        value += cash / ((1 + discount_rate) ** (i + 1))

    terminal_value = fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    value += terminal_value / ((1 + discount_rate) ** len(fcf))

    # Simple AI-style risk score
    volatility = max(fcf) - min(fcf)
    risk_score = min(100, int((volatility / abs(sum(fcf))) * 100))

    return jsonify({
        "ticker": ticker,
        "dcf_value": round(value / 1e9, 2),  # billions
        "risk_score": risk_score
          })
    
 if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    

