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

@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Missing ticker"}), 400

    stock = yf.Ticker(ticker)

    cashflow = stock.cashflow
    if cashflow is None or cashflow.empty:
        return jsonify({"error": "No cash flow data"}), 400

    operating_cf = cashflow.loc["Total Cash From Operating Activities"][0]
    capex = abs(cashflow.loc["Capital Expenditures"][0])
    free_cash_flow = operating_cf - capex

    price_data = stock.history(period="6mo")
    returns = price_data["Close"].pct_change().dropna()

    volatility = returns.std() * np.sqrt(252)
    price = price_data["Close"].iloc[-1]
    peak = price_data["Close"].max()
    drawdown = (peak - price) / peak

    dcf_value = true_dcf(free_cash_flow)
    valuation_gap = abs(dcf_value - price) / price
    risk = ai_risk(volatility, valuation_gap, drawdown)

    return jsonify({
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "dcf": round(dcf_value, 2),
        "risk": risk
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
@app.route("/")
def home():
    return "DCF Backend is running. Use /analyze?ticker=AAPL"

