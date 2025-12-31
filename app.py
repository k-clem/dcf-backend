from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import time
import os

app = Flask(__name__)
CORS(app)

# --------------------
# Simple in-memory cache
# --------------------
CACHE = {}
CACHE_TTL = 60 * 10  # 10 minutes


@app.route("/")
def health():
    return "DCF backend running", 200


@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker")

    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    ticker = ticker.upper()

    # ---- CACHE CHECK ----
    cached = CACHE.get(ticker)
    if cached and time.time() - cached["timestamp"] < CACHE_TTL:
        cached_data = cached["data"]
        cached_data["status"] = "cached"
        return jsonify(cached_data)

    try:
        stock = yf.Ticker(ticker)

        # ---- CASH FLOW ----
        cashflow = stock.cashflow
        if cashflow is None or cashflow.empty:
            return jsonify({"error": "No cash flow data available"}), 404

        if "Free Cash Flow" not in cashflow.index:
            return jsonify({"error": "Free Cash Flow not found"}), 404

        fcf_series = cashflow.loc["Free Cash Flow"].dropna()
        fcf = list(reversed(fcf_series.values))[:4]

        if len(fcf) < 2:
            return jsonify({"error": "Insufficient cash flow history"}), 400

        # ---- DCF CALCULATION ----
        discount_rate = 0.10
        terminal_growth = 0.025

        value = 0
        for i, cash in enumerate(fcf):
            value += cash / ((1 + discount_rate) ** (i + 1))

        terminal_value = fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        value += terminal_value / ((1 + discount_rate) ** len(fcf))

        # ---- PRICING DATA ----
        info = stock.info
        shares_outstanding = info.get("sharesOutstanding")
        current_price = info.get("currentPrice")

        if not shares_outstanding or not current_price:
            return jsonify({"error": "Missing pricing data"}), 500

        intrinsic_price = value / shares_outstanding

        # ---- VALUATION SIGNAL ----
        if intrinsic_price > current_price * 1.1:
            valuation_signal = "Undervalued"
        elif intrinsic_price < current_price * 0.9:
            valuation_signal = "Overvalued"
        else:
            valuation_signal = "Fairly Valued"

        # ---- AI RISK SCORE ----
        volatility = (max(fcf) - min(fcf)) / abs(sum(fcf))
        risk_score = min(100, round(volatility * 100))

        response_data = {
            "ticker": ticker,
            "dcf_value_billion": round(value / 1e9, 2),
            "intrinsic_price": round(intrinsic_price, 2),
            "current_price": round(current_price, 2),
            "valuation_signal": valuation_signal,
            "risk_score": risk_score,
            "years_used": len(fcf),
            "status": "complete"
        }

        # ---- CACHE STORE ----
        CACHE[ticker] = {
            "timestamp": time.time(),
            "data": response_data
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({
            "status": "rate_limited",
            "error": "Too many requests or upstream data unavailable",
            "details": str(e)
        }), 429


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
