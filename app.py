from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import numpy as np
import os

app = Flask(__name__)
CORS(app)

@app.route("/analyze")
def analyze():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    try:
        stock = yf.Ticker(ticker)
        cashflow = stock.cashflow

        if cashflow is None or cashflow.empty:
            return jsonify({"error": "No cash flow data available"}), 404

        # Free Cash Flow = Operating Cash Flow - CapEx
        if (
            "Total Cash From Operating Activities" not in cashflow.index
            or "Capital Expenditures" not in cashflow.index
        ):
            return jsonify({"error": "FCF fields missing"}), 404

        fcf_series = (
            cashflow.loc["Total Cash From Operating Activities"]
            - cashflow.loc["Capital Expenditures"]
        )

        fcf = fcf_series.dropna().values.tolist()

        if len(fcf) < 2:
            return jsonify({"error": "Insufficient FCF history"}), 404

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
            "risk_score": risk_score,
            "years_used": len(fcf)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
