from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("FMP_API_KEY")

@app.route("/")
def home():
    return jsonify({"status": "DCF backend running"})

@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    cf_url = (
        f"https://financialmodelingprep.com/api/v3/cash-flow-statement/"
        f"{ticker}?limit=5&apikey={API_KEY}"
    )

    response = requests.get(cf_url)
    data = response.json()

    if not data or "freeCashFlow" not in data[0]:
        return jsonify({"error": "No cash flow data"}), 404

    fcf = [year["freeCashFlow"] for year in data if year.get("freeCashFlow")]

    discount_rate = 0.10
    terminal_growth = 0.025

    value = 0
    for i, cash in enumerate(fcf):
        value += cash / ((1 + discount_rate) ** (i + 1))

    terminal_value = (
        fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    )
    value += terminal_value / ((1 + discount_rate) ** len(fcf))

    volatility = max(fcf) - min(fcf)
    risk_score = min(100, int((volatility / abs(sum(fcf))) * 100))

    return jsonify({
        "ticker": ticker.upper(),
        "dcf_value_billion": round(value / 1e9, 2),
        "risk_score": risk_score
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
