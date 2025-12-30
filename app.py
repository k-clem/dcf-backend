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

    stock = yf.Ticker(ticker)

    try:
        cashflow = stock.cashflow

        # 🔁 FALLBACK: try quarterly if annual missing
        if cashflow is None or cashflow.empty:
            cashflow = stock.quarterly_cashflow

        if cashflow is None or cashflow.empty:
            return jsonify({
                "ticker": ticker.upper(),
                "status": "queued",
                "message": "Cash flow data temporarily unavailable, retry later"
            }), 202

        # Normalize possible Yahoo field names
        op_fields = [
            "Total Cash From Operating Activities",
            "Operating Cash Flow"
        ]

        capex_fields = [
            "Capital Expenditures",
            "Capital Expenditure"
        ]

        ocf = None
        capex = None

        for f in op_fields:
            if f in cashflow.index:
                ocf = cashflow.loc[f]
                break

        for f in capex_fields:
            if f in cashflow.index:
                capex = cashflow.loc[f]
                break

        if ocf is None or capex is None:
            return jsonify({
                "ticker": ticker.upper(),
                "status": "queued",
                "message": "Required cash flow fields missing"
            }), 202

        fcf = (ocf - capex).dropna().values.tolist()

        if len(fcf) < 2:
            return jsonify({
                "ticker": ticker.upper(),
                "status": "queued",
                "message": "Insufficient historical cash flow"
            }), 202

        # DCF
        discount_rate = 0.10
        terminal_growth = 0.025

        value = 0
        for i, cash in enumerate(fcf):
            value += cash / ((1 + discount_rate) ** (i + 1))

        terminal_value = (
            fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        )
        value += terminal_value / ((1 + discount_rate) ** len(fcf))

        # AI Risk Score
        volatility = np.std(fcf) / abs(np.mean(fcf))
        risk_score = min(100, int(volatility * 100))

        return jsonify({
            "ticker": ticker.upper(),
            "dcf_value_billion": round(value / 1e9, 2),
            "risk_score": risk_score,
            "years_used": len(fcf),
            "status": "complete"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
