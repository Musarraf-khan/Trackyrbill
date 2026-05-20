from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os
import pickle
from werkzeug.utils import secure_filename
from receipt_model import process_receipt
from insights import predict_next_month, daily_forecast, predict_category, spending_insight
from bson.objectid import ObjectId

# Loading Environment
load_dotenv()

app = Flask(__name__)

# Secret Key for Session Encryption
app.secret_key = os.getenv("SECRET_KEY")

bcrypt = Bcrypt(app)

# MongoDB Connection
client = MongoClient(os.getenv("MONGO_URI"))
db = client["expensiqo"]
users = db["users"]
transactions = db["transactions"]
pending = db["pending_payments"]

# Page Routes
@app.route("/")
def home():
    return render_template("trackyrbill_main.html")

@app.route("/red-login")
def red_login():
    return render_template("auth v3.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    confirm = data.get('confirm', '')

    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    if password != confirm:
        return jsonify({'success': False, 'message': 'Passwords do not match.'}), 400

    if users.find_one({"email": email}):
        return jsonify({'success': False, 'message': 'Email is already registered.'}), 409

    # Hash password (encryption)
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

    # Insert user data into DB
    users.insert_one({
        'name': name,
        "email": email,
        "password": hashed_password
    })

    return jsonify({'success': True, 'message': 'Registration successful!'}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = users.find_one({"email": email})
    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401

    session['user_email'] = email
    session['user_name'] = user['name']

    return jsonify({'success': True, 'message': 'Login successful!', 'redirect': '/dashboard'}), 200

@app.route("/dashboard")
def dashboard():
    if "user_email" in session:
        user_data = users.find_one({"email": session["user_email"]})
        return render_template("dashboard_v20.html", user=user_data)

    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# Dashboard Routes
@app.route("/add-expense", methods=["POST"])
def add_expense():
    print("Route triggered")
    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    data = request.get_json()

    expense = {
        "user_email": session["user_email"],
        "title": data["title"],
        "amount": float(data["amount"]),
        "date": data["date"],
        "category": data["category"],
        "method": data["method"],
        "note": data.get("note", ""),
        "status": data["status"]
    }
    result = transactions.insert_one(expense)

    return {
        "message": "Expense added successfully",
        "success": True,
        "id": str(result.inserted_id)   
    }

@app.route("/get-expenses", methods=["GET"])
def get_expenses():
    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    user_email = session["user_email"]

    # Fetch newest first
    user_expenses = list(
        transactions.find(
            {"user_email": user_email}
            # {"_id": 0}
        ).sort("date", -1)
    )
    
    for d in user_expenses:
        d["_id"] = str(d["_id"])

    return {"expenses": user_expenses}

@app.route("/delete-expense/<id>", methods=["DELETE"])
def delete_expense(id):

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    try:
        transactions.delete_one({
            "_id": ObjectId(id),
            "user_email": session["user_email"]
        })

        return {"success": True}

    except Exception as e:
        return {"error": str(e)}, 500


# Graph Updates Routes
@app.route("/yearly-analytics")
def yearly_analytics():
    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    year = request.args.get("year")
    user_email = session["user_email"]

    expenses = list(transactions.find({
        "user_email": user_email,
        "date": {"$regex": f"^{year}"}
    }))

    # ----- Monthly totals -----
    monthly_totals = [0]*12

    for exp in expenses:
        month = int(exp["date"][5:7]) - 1
        monthly_totals[month] += float(exp["amount"])

    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

    # ----- Category totals -----
    category_totals = {}

    for exp in expenses:
        cat = exp["category"]
        amt = float(exp["amount"])

        category_totals[cat] = category_totals.get(cat, 0) + amt

    return {
        "line_labels": months,
        "line_values": monthly_totals,
        "pie_labels": list(category_totals.keys()),
        "pie_values": list(category_totals.values())
    }

@app.route("/category-analytics")
def category_analytics():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    user_email = session["user_email"]
    year  = request.args.get("year")
    month = request.args.get("month")

    query = {"user_email": user_email}

    if month == "all":
        query["date"] = {"$regex": f"^{year}"}
    else:
        query["date"] = {"$regex": f"^{year}-{month.zfill(2)}"}

    expenses = list(transactions.find(query))

    category_totals = {}

    for exp in expenses:
        cat = exp["category"]
        amt = float(exp["amount"])

        category_totals[cat] = category_totals.get(cat, 0) + amt

    return {
        "pie_labels": list(category_totals.keys()),
        "pie_values": list(category_totals.values())
    }

@app.route("/weekly-analytics")
def weekly_analytics():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    user_email = session["user_email"]

    today = datetime.today()
    week_totals = [0]*7
    labels = []

    for i in range(6,-1,-1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%a"))

        date_str = day.strftime("%Y-%m-%d")

        expenses = list(transactions.find({
            "user_email": user_email,
            "date": date_str
        }))

        total = sum(float(e["amount"]) for e in expenses)

        week_totals[6-i] = total

    return {
        "week_labels": labels,
        "week_values": week_totals
    }

# Expenditure Route
@app.route("/total-expense", methods=["GET"])
def total_expense():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    pipeline = [
        {
            "$match": {
                "user_email": session["user_email"],
                "status": "completed"   # only completed payments
            }
        },
        {
            "$group": {
                "_id": None,
                "total": { "$sum": "$amount" }
            }
        }
    ]

    result = list(transactions.aggregate(pipeline))

    total = result[0]["total"] if result else 0

    return {"total": total}



# Receipt Scanning Route
UPLOAD_FOLDER="uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"]=UPLOAD_FOLDER

@app.route("/scan-receipt", methods=["POST"])
def scan_receipt():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    if "receipt" not in request.files:
        return {"error": "No file uploaded"}, 400

    file=request.files["receipt"]

    filename=secure_filename(file.filename)
    filepath=os.path.join(app.config["UPLOAD_FOLDER"], filename)

    file.save(filepath)

    # Send image to receipt model
    result=process_receipt(filepath)

    category=result.get("category","")
    amount=float(result.get("amount", 0))
    date=result.get("date", datetime.today().strftime("%Y-%m-%d"))
    raw_text=result.get("raw_text", "")

    expense = {
        "user_email": session["user_email"],
        "title": f"{category}: Receipt Expense",
        "amount": amount,
        "date": date,
        "category": category,
        "method": "receipt",
        "status": "completed",
        # "note": raw_text,
        # "created_at": datetime.utcnow()
    }

    transactions.insert_one(expense)

    return {
        "success": True,
        # "expense": expense
    }

# Pending Payments Routes
@app.route("/add-pending", methods=["POST"])
def add_pending():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    data = request.get_json()

    payment = {
        "user_email": session["user_email"],
        "name": data["name"],
        "upiId": data.get("upiId", ""),
        "amount": float(data["amount"]),
        "category": data.get("category", "miscellaneous"),
        "date": data["date"],
        "status": "pending"
    }

    result = pending.insert_one(payment)

    return {
        "success": True,
        "id": str(result.inserted_id)   #send _id back
    }

@app.route("/get-pending")
def get_pending():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    data = list(pending.find({"user_email": session["user_email"]}))

    # Convert ObjectId → string
    for d in data:
        d["_id"] = str(d["_id"])

    return {"pending": data}

@app.route("/delete-pending/<id>", methods=["DELETE"])
def delete_pending(id):

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    pending.delete_one({
        "_id": ObjectId(id),
        "user_email": session["user_email"]
    })

    return {"success": True}

# update pending payment status to 'completed'
@app.route("/update-expense-status/<id>", methods=["POST"])
def update_expense_status(id):

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    data = request.get_json()
    status = data.get("status", "completed")

    transactions.update_one(
        {
            "_id": ObjectId(id),
            "user_email": session["user_email"]
        },
        {
            "$set": {"status": status}
        }
    )

    return {"success": True}

# Profile Routes
@app.route("/get-profile", methods=["GET"])
def get_profile():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    user = users.find_one(
        {"email": session["user_email"]},
        {"_id": 0, "name": 1, "email": 1, "monthly_goal": 1}
    )

    return user if user else {}

@app.route("/update-profile", methods=["POST"])
def update_profile():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    data = request.json

    users.update_one(
        {"email": session["user_email"]},
        {
            "$set": {
                "name": data.get("name"),
                "monthly_goal": data.get("monthly_goal")
            }
        }
    )

    # update session also (important)
    session["user_name"] = data.get("name")

    return {"success": True}

@app.route("/change-password", methods=["POST"])
def change_password():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    data = request.json

    current_password = data.get("current_password")
    new_password = data.get("new_password")

    user = users.find_one({"email": session["user_email"]})

    # Checking current password
    if not bcrypt.check_password_hash(user["password"], current_password):
        return {"error": "Current password is incorrect"}

    # Preventing same password reuse
    if bcrypt.check_password_hash(user["password"], new_password):
        return {"error": "New password cannot be same as current password"}

    # Hashing new password
    hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')

    users.update_one(
        {"email": session["user_email"]},
        {"$set": {"password": hashed_password}}
    )

    return {"success": True}
    # return jsonify({"success": True})


# Insights Routes with functions from insights.py
def get_user_expenses():
    user_email = session.get("user_email")

    data = list(transactions.find({"user_email": user_email}))

    # Convert ObjectId to string
    for d in data:
        d["_id"] = str(d["_id"])

    return data

@app.route("/smart-insights")
def smart_insights():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    expenses = get_user_expenses()

    insight_data = spending_insight(expenses)

    return {
        "next_month_prediction": predict_next_month(expenses),
        "daily_forecast": daily_forecast(expenses),
        "next_category": predict_category(expenses),
        "insight": insight_data["text"],
        "insight_type": insight_data["type"]
    }

# Monthly Saving Card
def saving_goal_card(expenses, goal):

    from datetime import datetime
    now = datetime.now()

    total = 0

    for e in expenses:
        try:
            date = datetime.strptime(e["date"], "%Y-%m-%d")
            if date.month == now.month and date.year == now.year:
                total += float(e["amount"])
        except:
            continue

    remaining = goal - total

    exceeded = abs(remaining) if remaining < 0 else 0

    progress = (total / goal) * 100 if goal > 0 else 0
    progress = min(progress, 100)

    return {
        "remaining": max(remaining, 0),
        "progress": round(progress, 1),
        "exceeded": round(exceeded, 2)
    }

@app.route("/monthly-saving")
def monthly_saving():

    if "user_email" not in session:
        return {"error": "Unauthorized"}, 401

    expenses = get_user_expenses()

    user = users.find_one({"email": session["user_email"]})
    goal = user.get("monthly_goal", 0)

    saving_data = saving_goal_card(expenses, goal)

    return {
        "saving_card": saving_data
    }

if __name__ == "__main__":
    app.run(debug=True)