from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import time
import os

app = Flask(__name__)
CORS(app)

# --------------------
# Lightweight cache
# --------------------
CACHE = {}
CACHE_TTL = 60 * 15  # 15 minutes


@app.route("/")
def home():
    return "DCF backend running", 200


@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker")

    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    ticker = ticker.upper()

    # ---- CACHE CHECK ----
    if ticker in CACHE:
        cached = CACHE[ticker]
        if time.time() - cached["time"] < CACHE_TTL:
            data = cached["data"]
            data["status"] = "cached"
            return jsonify(data)

    try:
        stock = yf.Ticker(ticker)

        # ---- FREE CASH FLOW (LIGHT CALL) ----
        cashflow = stock.cashflow
        if cashflow is None or cashflow.empty:
            return jsonify({"error": "No cash flow data"}), 404

        if "Free Cash Flow" not in cashflow.index:
            return jsonify({"error": "FCF missing"}), 404

        fcf_series = cashflow.loc["Free Cash Flow"].dropna()
        fcf = list(reversed(fcf_series.values))[:4]

        if len(fcf) < 2:
            return jsonify({"error": "Insufficient cash flow history"}), 400

        # ---- DCF ----
        discount_rate = 0.10
        terminal_growth = 0.025

        value = 0
        for i, cash in enumerate(fcf):
            value += cash / ((1 + discount_rate) ** (i + 1))

        terminal_value = fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        value += terminal_value / ((1 + discount_rate) ** len(fcf))

        # ---- PRICE DATA (MINIMAL INFO ACCESS) ----
        shares = stock.info.get("sharesOutstanding")
        price = stock.info.get("currentPrice")

        if not shares or not price:
            return jsonify({"error": "Price data unavailable"}), 500

        intrinsic_price = value / shares

        # ---- VALUATION SIGNAL ----
        if intrinsic_price > price * 1.1:
            signal = "Undervalued"
        elif intrinsic_price < price * 0.9:
            signal = "Overvalued"
        else:
            signal = "Fairly Valued"

        # ---- RISK SCORE ----
        volatility = (max(fcf) - min(fcf)) / abs(sum(fcf))
        risk_score = min(100, round(volatility * 100))

        response = {
            "ticker": ticker,
            "intrinsic_price": round(intrinsic_price, 2),
            "current_price": round(price, 2),
            "valuation_signal": signal,
            "risk_score": risk_score,
            "years_used": len(fcf),
            "status": "complete"
        }

        CACHE[ticker] = {
            "time": time.time(),
            "data": response
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({
            "status": "rate_limited",
            "error": "Upstream data unavailable",
            "details": str(e)
        }), 429


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
