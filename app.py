from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import time

app = Flask(__name__)
CORS(app)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

if not FINNHUB_API_KEY:
    raise RuntimeError("FINNHUB_API_KEY not set")

BASE_URL = "https://finnhub.io/api/v1"


def fetch_json(url, params):
    params["token"] = FINNHUB_API_KEY
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def calculate_dcf_per_share(fcf_list, shares_outstanding):
    discount_rate = 0.10
    terminal_growth = 0.025

    value = 0
    for i, fcf in enumerate(fcf_list):
        value += fcf / ((1 + discount_rate) ** (i + 1))

    terminal_value = (
        fcf_list[-1] * (1 + terminal_growth)
    ) / (discount_rate - terminal_growth)

    value += terminal_value / ((1 + discount_rate) ** len(fcf_list))

    return value / shares_outstanding


def risk_score_from_fcf(fcf_list):
    volatility = max(fcf_list) - min(fcf_list)
    avg = sum(fcf_list) / len(fcf_list)
    score = (volatility / abs(avg)) * 100
    return min(100, round(score))


@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    try:
        # Company metrics
        metrics = fetch_json(
            f"{BASE_URL}/stock/metric",
            {"symbol": ticker, "metric": "all"}
        )

        shares = metrics.get("metric", {}).get("sharesOutstanding")
        if not shares:
            return jsonify({"error": "Shares outstanding unavailable"}), 400

        # Cash flow
        cashflow = fetch_json(
            f"{BASE_URL}/stock/cash-flow",
            {"symbol": ticker}
        )

        annual = cashflow.get("cashFlow", {}).get("annual", [])
        fcf_list = [
            year["freeCashFlow"]
            for year in annual
            if year.get("freeCashFlow") and year["freeCashFlow"] > 0
        ][:5]

        if len(fcf_list) < 3:
            return jsonify({"error": "Insufficient cash flow history"}), 400

        # Price
        quote = fetch_json(
            f"{BASE_URL}/quote",
            {"symbol": ticker}
        )
        current_price = quote.get("c")

        intrinsic_value = calculate_dcf_per_share(fcf_list, shares)
        risk = risk_score_from_fcf(fcf_list)

        valuation = (
            "Undervalued"
            if intrinsic_value > current_price
            else "Overvalued"
        )

        return jsonify({
            "ticker": ticker,
            "price_per_share": round(current_price, 2),
            "intrinsic_value_per_share": round(intrinsic_value, 2),
            "valuation_status": valuation,
            "risk_score": risk,
            "years_used": len(fcf_list),
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
