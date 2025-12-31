from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import time
import os

app = Flask(__name__)
CORS(app)

CACHE = {}
CACHE_TTL = 60 * 20  # 20 minutes


@app.route("/")
def home():
    return "DCF-lite backend running", 200


@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    ticker = ticker.upper()

    # ---- CACHE ----
    if ticker in CACHE:
        cached = CACHE[ticker]
        if time.time() - cached["time"] < CACHE_TTL:
            data = cached["data"]
            data["status"] = "cached"
            return jsonify(data)

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        price = info.get("currentPrice")
        eps = info.get("trailingEps")
        shares = info.get("sharesOutstanding")

        if not price or not eps or not shares:
            return jsonify({"error": "Insufficient market data"}), 404

        # ---- FCF PROXY ----
        payout_ratio = 0.6  # conservative
        fcf_per_share = eps * payout_ratio
        growth = 0.05
        discount = 0.10
        terminal = 0.025
        years = 5

        value = 0
        fcf = fcf_per_share

        for i in range(1, years + 1):
            fcf *= (1 + growth)
            value += fcf / ((1 + discount) ** i)

        terminal_value = (fcf * (1 + terminal)) / (discount - terminal)
        value += terminal_value / ((1 + discount) ** years)

        intrinsic_price = round(value, 2)

        # ---- VALUATION ----
        if intrinsic_price > price * 1.15:
            signal = "Undervalued"
        elif intrinsic_price < price * 0.85:
            signal = "Overvalued"
        else:
            signal = "Fairly Valued"

        # ---- RISK SCORE ----
        beta = info.get("beta", 1)
        pe = info.get("trailingPE", 20)

        risk_score = min(100, int(beta * 30 + pe * 1.5))

        response = {
            "ticker": ticker,
            "intrinsic_price": intrinsic_price,
            "current_price": round(price, 2),
            "valuation_signal": signal,
            "risk_score": risk_score,
            "years_used": years,
            "status": "complete"
        }

        CACHE[ticker] = {
            "time": time.time(),
            "data": response
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": "Market data unavailable",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
