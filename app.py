from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import time

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("FINNHUB_API_KEY")
BASE = "https://finnhub.io/api/v1"

if not API_KEY:
    raise RuntimeError("FINNHUB_API_KEY not set")


def fetch(url, params):
    params["token"] = API_KEY
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


def get_shares(ticker):
    profile = fetch(f"{BASE}/stock/profile2", {"symbol": ticker})
    return profile.get("shareOutstanding")


def get_free_cash_flow(ticker):
    data = fetch(f"{BASE}/stock/financials-reported", {"symbol": ticker})
    reports = data.get("data", [])

    fcf = []
    for r in reports:
        cf = r.get("report", {}).get("cf", {})
        operating = cf.get("Net cash flow from operating activities")
        capex = cf.get("Capital expenditure")

        if operating and capex:
            fcf.append(operating - abs(capex))

        if len(fcf) == 5:
            break

    return fcf


def dcf_per_share(fcf, shares):
    discount = 0.10
    terminal_growth = 0.025

    pv = 0
    for i, cash in enumerate(fcf):
        pv += cash / ((1 + discount) ** (i + 1))

    terminal = (fcf[-1] * (1 + terminal_growth)) / (discount - terminal_growth)
    pv += terminal / ((1 + discount) ** len(fcf))

    return pv / shares


def risk_score(fcf):
    vol = max(fcf) - min(fcf)
    avg = sum(fcf) / len(fcf)
    return min(100, round((vol / abs(avg)) * 100))


@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    try:
        shares = get_shares(ticker)
        if not shares:
            return jsonify({"error": "Shares outstanding unavailable"}), 400

        time.sleep(0.4)

        fcf = get_free_cash_flow(ticker)
        if len(fcf) < 3:
            return jsonify({"error": "Insufficient cash flow data"}), 400

        time.sleep(0.4)

        quote = fetch(f"{BASE}/quote", {"symbol": ticker})
        price = quote.get("c")

        intrinsic = dcf_per_share(fcf, shares)
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
