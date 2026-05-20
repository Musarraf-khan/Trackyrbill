import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime
from collections import Counter
from bson import ObjectId

def predict_next_month(expenses):
    monthly = {}

    for exp in expenses:
        if not exp.get("date") or not exp.get("amount"):
            continue

        date = datetime.strptime(exp["date"], "%Y-%m-%d")
        key = f"{date.year}-{date.month}"

        monthly[key] = monthly.get(key, 0) + exp["amount"]

    if len(monthly) < 2:
        return 0

    # Sort months
    sorted_months = sorted(monthly.items())

    X = []
    y = []

    for i, (month, amount) in enumerate(sorted_months):
        X.append([i])
        y.append(amount)

    model = LinearRegression()
    model.fit(X, y)

    next_index = len(X)
    prediction = model.predict([[next_index]])

    return round(float(prediction[0]), 2)

def daily_forecast(expenses):
    if not expenses:
        return 0

    total = sum(e["amount"] for e in expenses if e.get("amount"))

    dates = [datetime.strptime(e["date"], "%Y-%m-%d") for e in expenses if e.get("date")]

    if not dates:
        return 0

    days = (max(dates) - min(dates)).days + 1

    if days == 0:
        return total

    return round(total / days, 2)

def predict_category(expenses):
    recent = expenses[-15:]  # last 15

    categories = [e.get("category", "Others") for e in recent]

    if not categories:
        return "Others"

    count = Counter(categories)

    return count.most_common(1)[0][0]

def spending_insight(expenses):
    monthly = {}

    for exp in expenses:
        date = datetime.strptime(exp["date"], "%Y-%m-%d")
        key = f"{date.year}-{date.month}"

        monthly[key] = monthly.get(key, 0) + exp["amount"]

    if len(monthly) < 2:
        return {"text": "Not enough data", "type": "neutral"}

    sorted_months = sorted(monthly.items())

    last = sorted_months[-1][1]
    prev = sorted_months[-2][1]

    if prev == 0:
        return {"text": "No comparison available", "type": "neutral"}

    change = ((last - prev) / prev) * 100

    if change > 0:
        return {
            "text": f"You spent {round(change,1)}% more than last month",
            "type": "increase"
        }
    else:
        return {
            "text": f"You spent {abs(round(change,1))}% less than last month",
            "type": "decrease"
        }