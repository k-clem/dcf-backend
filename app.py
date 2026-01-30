from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

@app.route("/analyze")
def analyze():
    try:
        ticker = request.args.get("ticker")
        if not ticker:
            return jsonify({"error": "Ticker required"}), 400

        stock = yf.Ticker(ticker)
        info = stock.info

        price = info.get("currentPrice")
        eps = info.get("trailingEps")
        shares = info.get("sharesOutstanding")

        if not price or not eps or not shares:
            return jsonify({"error": "Market data unavailable"}), 400

        # --- Valuation assumptions ---
        growth_rate = 0.08
        discount_rate = 0.10
        years = 5
        terminal_multiple = 15

        # Project EPS
        projected_eps = eps * ((1 + growth_rate) ** years)
        fair_value = (projected_eps * terminal_multiple) / ((1 + discount_rate) ** years)

        valuation_gap = (fair_value - price) / price

        # Risk score (0 = low risk, 100 = high risk)
        risk_score = min(100, max(1, int(abs(valuation_gap) * 100)))

        verdict = "Undervalued" if fair_value > price else "Overvalued"

        return jsonify({
            "ticker": ticker.upper(),
            "price": round(price, 2),
            "fair_value": round(fair_value, 2),
            "valuation": verdict,
            "risk_score": risk_score,
            "years_used": years,
            "status": "complete"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
