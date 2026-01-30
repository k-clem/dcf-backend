from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("FINNHUB_API_KEY")
BASE = "https://finnhub.io/api/v1"

if not API_KEY:
    raise RuntimeError("FINNHUB_API_KEY not set")


def fetch(url, params):
    params["token"] = API_KEY
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_shares_outstanding(ticker):
    # Try metrics first
    metrics = fetch(f"{BASE}/stock/metric", {
        "symbol": ticker,
        "metric": "all"
    })
    shares = metrics.get("metric", {}).get("sharesOutstanding")
    if shares:
        return shares

    # Fallback: company profile
    profile = fetch(f"{BASE}/stock/profile2", {
        "symbol": ticker
    })
    return profile.get("shareOutstanding")


def calculate_dcf_per_share(fcf, shares):
    discount = 0.10
    terminal_growth = 0.025

    value = 0
    for i, cash in enumerate(fcf):
        value += cash / ((1 + discount) ** (i + 1))

    terminal = (fcf[-1] * (1 + terminal_growth)) / (discount - terminal_growth)
    value += terminal / ((1 + discount) ** len(fcf))

    return value / shares


def risk_score(fcf):
    vol = max(fcf) - min(fcf)
    avg = sum(fcf) / len(fcf)
    score = (vol / abs(avg)) * 100
    return min(100, round(score))


@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    try:
        shares = get_shares_outstanding(ticker)
        if not shares:
            return jsonify({"error": "Shares outstanding unavailable"}), 400

        cashflow = fetch(f"{BASE}/stock/cash-flow", {
            "symbol": ticker
        })

        annual = cashflow.get("cashFlow", {}).get("annual", [])
        fcf = [
            y["freeCashFlow"]
            for y in annual
            if y.get("freeCashFlow") and y["freeCashFlow"] > 0
        ][:5]

        if len(fcf) < 3:
            return jsonify({"error": "Insufficient cash flow data"}), 400

        quote = fetch(f"{BASE}/quote", {"symbol": ticker})
        price = quote.get("c")

        intrinsic = calculate_dcf_per_share(fcf, shares)
        risk = risk_score(fcf)

        valuation = "Undervalued" if intrinsic > price else "Overvalued"

        return jsonify({
            "ticker": ticker,
            "price_per_share": round(price, 2),
            "intrinsic_value_per_share": round(intrinsic, 2),
            "valuation_status": valuation,
            "risk_score": risk,
            "years_used": len(fcf),
            "status": "complete"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
