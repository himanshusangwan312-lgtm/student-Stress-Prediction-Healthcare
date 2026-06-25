from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import pandas as pd
import numpy as np
import os
import pickle
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import urllib.parse

app = Flask(__name__)
app.secret_key = "supersecretkey123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = "database.db"

# ==============================
# DATABASE INIT
# ==============================
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER,
            rating INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT,
            intent TEXT,
            confidence REAL,
            crisis_flag INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("SELECT * FROM admin WHERE username=?", ("admin",))
    if not c.fetchone():
        hashed_pw = generate_password_hash("admin123")
        c.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ("admin", hashed_pw))

    conn.commit()
    conn.close()

init_db()

# ==============================
# LOAD ML MODELS
# ==============================
model = pickle.load(open(os.path.join(BASE_DIR, "model", "depression_model.pkl"), "rb"))
intent_model = pickle.load(open(os.path.join(BASE_DIR, "intent_model", "intent_model.pkl"), "rb"))
vectorizer = pickle.load(open(os.path.join(BASE_DIR, "intent_model", "vectorizer.pkl"), "rb"))

def predict_intent(text):
    text_vec = vectorizer.transform([text])
    intent = intent_model.predict(text_vec)[0]
    prob = intent_model.predict_proba(text_vec)
    confidence = round(np.max(prob) * 100, 2)
    return intent, confidence

# ==============================
# LOAD CSV DATA
# ==============================
df1 = pd.read_csv("hospital_directory_master_10000.csv", low_memory=False)
df2 = pd.read_csv("hospital_directory_master_50000.csv", low_memory=False)
df3 = pd.read_csv("clean_doctors.csv", low_memory=False)

df = pd.concat([df1, df2, df3], ignore_index=True)

# ==============================
# AUTO COLUMN DETECT
# ==============================
def find_column(possible):
    for p in possible:
        for c in df.columns:
            if p in c.lower():
                return c
    return None

STATE = find_column(["state"])
CITY = find_column(["city", "district", "location"])
DOCTOR = find_column(["doctor"])
HOSPITAL = find_column(["hospital", "clinic", "facility", "medical"])
NAME = DOCTOR if DOCTOR else find_column(["name"])
PHONE = find_column(["phone", "mobile", "contact"])
SPEC = find_column(["special", "dept", "stream"])

# ==============================
# RATING FUNCTION
# ==============================
def get_average_rating(doc_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT AVG(rating) FROM ratings WHERE doctor_id=?", (doc_id,))
    avg = c.fetchone()[0]
    conn.close()
    return round(avg, 1) if avg else 0

# ==============================
# ADMIN ANALYTICS
# ==============================
def get_admin_analytics():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM chat_logs")
    total_chats = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM chat_logs WHERE crisis_flag=1")
    crisis_count = c.fetchone()[0]

    c.execute("SELECT AVG(confidence) FROM chat_logs")
    avg_confidence = c.fetchone()[0]

    c.execute("""
        SELECT doctor_id, AVG(rating), COUNT(*)
        FROM ratings GROUP BY doctor_id
        ORDER BY AVG(rating) DESC LIMIT 5
    """)
    top = c.fetchall()

    conn.close()

    top_doctors = []
    for t in top:
        if t[0] in df.index:
            top_doctors.append({
                "name": str(df.loc[t[0]].get(NAME, "")),
                "avg": round(t[1],1),
                "count": t[2]
            })

    return total_ratings, total_chats, crisis_count, round(avg_confidence or 0,2), top_doctors

# ==============================
# ROUTES
# ==============================
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/emergency")
def emergency():
    return render_template("emergency.html")

# ==============================
# ADMIN LOGIN
# ==============================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM admin WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["admin"] = username
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid Credentials", "danger")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

# ==============================
# ADMIN DASHBOARD (UPDATED)
# ==============================
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    total_doctors = len(df)
    total_states = len(df[STATE].dropna().unique())
    total_cities = len(df[CITY].dropna().unique())

    total_ratings, total_chats, crisis_count, avg_conf, top_doctors = get_admin_analytics()

    # 🔥 CHAT LOGS FETCH
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM chat_logs ORDER BY id DESC LIMIT 50")
    logs = c.fetchall()
    conn.close()

    chat_logs = [
        {
            "user_message": i[1],
            "intent": i[2],
            "confidence": i[3],
            "crisis_flag": i[4],
            "timestamp": i[5]
        } for i in logs
    ]

    return render_template(
        "admin_dashboard.html",
        total_doctors=total_doctors,
        total_states=total_states,
        total_cities=total_cities,
        total_ratings=total_ratings,
        total_chats=total_chats,
        crisis_count=crisis_count,
        avg_confidence=avg_conf,
        top_doctors=top_doctors,
        chat_logs=chat_logs
    )

# ==============================
# CSV EXPORT
# ==============================
@app.route("/export_csv")
def export_csv():
    conn = sqlite3.connect(DATABASE)
    df_logs = pd.read_sql_query("SELECT * FROM chat_logs", conn)
    conn.close()

    file_path = "chat_logs.csv"
    df_logs.to_csv(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# ==============================
# CHATBOT (UPDATED WITH LOGGING)
# ==============================
@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")

@app.route("/get_reply", methods=["POST"])
def get_reply():
    user_message = request.form["msg"].lower()
    intent, confidence = predict_intent(user_message)

    responses = {
        "greeting": "Hello! How can I help you today?",
        "depression": "I'm really sorry you're feeling this way.",
        "anxiety": "Try deep breathing exercises.",
        "nutrition_help": "Maintain balanced diet.",
        "lifestyle_help": "Sleep well and exercise.",
        "doctor_search": "Use Doctor Finder section.",
        "emergency": "Contact emergency services immediately."
    }

    reply = responses.get(intent, "Can you explain more?")

    # 🔥 CRISIS DETECTION
    crisis_flag = 1 if any(word in user_message for word in ["suicide", "kill myself", "die"]) else 0

    # 🔥 SAVE CHAT LOG
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO chat_logs (user_message, intent, confidence, crisis_flag)
        VALUES (?, ?, ?, ?)
    """, (user_message, intent, confidence, crisis_flag))
    conn.commit()
    conn.close()

    return f"{reply}\n(Intent: {intent} | {confidence}%)"
# ==============================
# DOCTOR FINDER (FIXED ROUTE)
# ==============================
@app.route("/doctors", methods=["GET", "POST"])
def doctors():

    states = sorted(df[STATE].dropna().astype(str).unique())
    cities = []
    results = []

    selected_state = ""
    selected_city = ""
    search_query = ""

    temp = df.copy()

    if request.method == "POST":
        selected_state = request.form.get("state", "").strip()
        selected_city = request.form.get("city", "").strip()
        search_query = request.form.get("search", "").strip().lower()

    if selected_state:
        temp = temp[temp[STATE].astype(str) == selected_state]
        cities = sorted(temp[CITY].dropna().astype(str).unique())

    if selected_city:
        temp = temp[temp[CITY].astype(str) == selected_city]

    if search_query:
        temp = temp[
            temp[NAME].astype(str).str.lower().str.contains(search_query, na=False) |
            temp[HOSPITAL].astype(str).str.lower().str.contains(search_query, na=False) |
            temp[SPEC].astype(str).str.lower().str.contains(search_query, na=False)
        ]

    for index, r in temp.head(50).iterrows():

        location = f"{r.get(HOSPITAL,'')} {r.get(CITY,'')} {r.get(STATE,'')}"
        map_link = "https://www.google.com/maps/search/" + urllib.parse.quote(location)

        results.append({
            "id": int(index),
            "doctor": str(r.get(NAME, "")),
            "hospital": str(r.get(HOSPITAL, "")),
            "city": str(r.get(CITY, "")),
            "state": str(r.get(STATE, "")),
            "phone": str(r.get(PHONE, "Not available")),
            "spec": str(r.get(SPEC, "General")),
            "rating": get_average_rating(int(index)),
            "map": map_link
        })

    return render_template(
        "doctors.html",
        states=states,
        cities=cities,
        results=results,
        selected_state=selected_state,
        selected_city=selected_city,
        search_query=search_query,
        page=1,
        total_pages=1
    )


# ==============================
# DOCTOR DETAIL (REQUIRED)
# ==============================
@app.route("/doctor/<int:doc_id>", methods=["GET", "POST"])
def doctor_detail(doc_id):

    if doc_id not in df.index:
        return "Doctor not found"

    if request.method == "POST":
        rating = int(request.form["rating"])
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("INSERT INTO ratings (doctor_id, rating) VALUES (?, ?)", (doc_id, rating))
        conn.commit()
        conn.close()
        return redirect(url_for("doctor_detail", doc_id=doc_id))

    r = df.loc[doc_id]

    location = f"{r.get(HOSPITAL,'')} {r.get(CITY,'')} {r.get(STATE,'')}"
    map_link = "https://www.google.com/maps/search/" + urllib.parse.quote(location)

    return render_template(
        "doctor_detail.html",
        doctor=str(r.get(NAME, "")),
        hospital=str(r.get(HOSPITAL, "")),
        city=str(r.get(CITY, "")),
        state=str(r.get(STATE, "")),
        phone=str(r.get(PHONE, "")),
        spec=str(r.get(SPEC, "")),
        rating=get_average_rating(doc_id),
        map=map_link
    )

# ==============================
# AJAX CITY FIX
# ==============================
@app.route("/get_cities/<state>")
def get_cities(state):
    temp = df[df[STATE].astype(str) == state]
    city_list = sorted(temp[CITY].dropna().astype(str).unique())
    return jsonify({"cities": city_list})
# ==============================
# ML PREDICTION (FIXED FOR YOUR FORM)
# ==============================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        age = float(request.form.get("age", 0))
        cgpa = float(request.form.get("cgpa", 0))
        anxiety = int(request.form.get("anxiety", 0))
        panic = int(request.form.get("panic", 0))
        year = int(request.form.get("year", 1))

        # 🔥 convert to model format (dummy mapping)
        sleep = 6 + (cgpa / 2)
        screen = 3 + anxiety
        activity = 1 if anxiety == 0 else 0
        social = 1 if panic == 0 else 0
        work = cgpa

        features = np.array([[age, sleep, screen, activity, social, work]])

        prediction_class = model.predict(features)[0]

        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(features)[0]
            risk_percent = round(max(prob) * 100, 2)
        else:
            risk_percent = int(prediction_class) * 50

        if prediction_class == 2:
            prediction = "HIGH STRESS"
            color = "red"
        elif prediction_class == 1:
            prediction = "MEDIUM STRESS"
            color = "orange"
        else:
            prediction = "LOW STRESS"
            color = "green"

        nutrition = "Eat balanced diet, reduce caffeine, drink more water."
        lifestyle = "Sleep 7-8 hours, reduce screen time, exercise regularly."

        return render_template(
            "result.html",
            prediction=prediction,
            risk=risk_percent,
            color=color,
            nutrition=nutrition,
            lifestyle=lifestyle
        )

    except Exception as e:
        return f"Error: {str(e)}"
# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    app.run(debug=True)