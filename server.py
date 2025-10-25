
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import sqlite3, os, requests, datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_PATH = "database.db"
ADMIN_EMAIL = "admin@turbo.com"

OSRM_ROUTE_URL = "http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"

def init_db():
    if not os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin_lat REAL,
                    origin_lon REAL,
                    dest_lat REAL,
                    dest_lon REAL,
                    distance_km REAL,
                    price INTEGER,
                    duration_s REAL,
                    created_at TEXT,
                    user_email TEXT
                )
            """)
            conn.commit()
            hashed = generate_password_hash("admin123")
            try:
                cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (ADMIN_EMAIL, hashed))
                conn.commit()
            except Exception:
                pass
            print("DB created and admin added")

@app.route("/")
def home():
    current_user = session.get("user")
    return render_template("index.html", current_user=current_user, admin_email=ADMIN_EMAIL)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email = request.form["email"]
        password = request.form["password"]
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email=?", (email,))
            user = cur.fetchone()
        if user and check_password_hash(user[2], password):
            session["user"] = email
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for("home"))
        flash("Credenciales incorrectas", "danger")
    return render_template("login.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        email = request.form["email"]
        password = request.form["password"]
        hashed = generate_password_hash(password)
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            try:
                cur.execute("INSERT INTO users (email,password) VALUES (?,?)", (email, hashed))
                conn.commit()
                flash("Cuenta creada", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Usuario ya existe", "warning")
    return render_template("signup.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user_email=session["user"], admin_email=ADMIN_EMAIL)

@app.route("/admin")
def admin():
    if "user" not in session or session["user"] != ADMIN_EMAIL:
        return redirect(url_for("login"))
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id,email FROM users")
        users = cur.fetchall()
    return render_template("admin.html", users=users)

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Sesión cerrada", "info")
    return redirect(url_for("home"))

@app.route("/calcular", methods=["POST"])
def calcular():
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "No JSON body"}), 400
    origin = payload.get("origin")
    dest = payload.get("destination")
    if not origin or not dest:
        return jsonify({"error": "origin and destination required"}), 400
    try:
        lat1 = float(origin.get("lat"))
        lon1 = float(origin.get("lon"))
        lat2 = float(dest.get("lat"))
        lon2 = float(dest.get("lon"))
    except Exception:
        return jsonify({"error": "invalid coordinates"}), 400
    try:
        url = OSRM_ROUTE_URL.format(lon1=lon1, lat1=lat1, lon2=lon2, lat2=lat2)
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        res = r.json()
        if "routes" not in res or not res["routes"]:
            return jsonify({"error": "No route found"}), 400
        route = res["routes"][0]
        dist_m = route["distance"]
        duration_s = route["duration"]
        geom = route.get("geometry")
        dist_km = round(dist_m / 1000, 3)
        precio = int(2500 + (dist_km * 900))
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""INSERT INTO calculations
                (origin_lat, origin_lon, dest_lat, dest_lon, distance_km, price, duration_s, created_at, user_email)
                VALUES (?,?,?,?,?,?,?,?,?)""" ,
                (lat1, lon1, lat2, lon2, dist_km, precio, duration_s, datetime.datetime.utcnow().isoformat(), session.get("user"))
            )
            conn.commit()
        return jsonify({
            "distance_km": dist_km,
            "duration_s": duration_s,
            "price": precio,
            "geometry": geom
        })
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Error contacting routing service", "detail": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "internal error", "detail": str(e)}), 500

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
