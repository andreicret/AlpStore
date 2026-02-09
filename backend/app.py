from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from jose import jwt
import requests
import os
from datetime import datetime
import time
import socket
from flask import Flask, jsonify, request, send_from_directory, make_response

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError



# Helpers: wait + db bootstrap

# Wait for DB to be ready
def wait_for_db(uri: str, retries=60, delay=2):
    eng = create_engine(uri, pool_pre_ping=True)
    for _ in range(retries):
        try:
            with eng.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return
        except OperationalError:
            time.sleep(delay)
    raise RuntimeError("DB not ready after waiting")

# Ensure alpstore DB exists (or create it)
def ensure_alpstore_db_exists(pg_host, pg_user, pg_password):
   
    try:
        conn = psycopg2.connect(
            host=pg_host,
            dbname="postgres",
            user=pg_user,
            password=pg_password
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM pg_database WHERE datname='alpstore';")
        exists = cur.fetchone()

        if not exists:
            cur.execute('CREATE DATABASE "alpstore";')
            print("Database alpstore created.")

        cur.close()
        conn.close()
    except Exception as e:
        print("Error checking/creating alpstore DB:", e)


# App setup
app = Flask(__name__)
CORS(app)

# PostgreSQL config (env from Docker)
PG_HOST = os.getenv("PG_HOST", "postgres")
PG_DB = os.getenv("PG_DB", "alpstore")
PG_USER = os.getenv("PG_USER", "keycloak")
PG_PASSWORD = os.getenv("PG_PASSWORD", "keycloak123")

# SQLAlchemy config
app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}/{PG_DB}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 120,
}

# ORM setup
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# HTTP timeouts for internal service calls
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "6"))

# Keycloak config
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080/realms/alpstore")
JWKS_URL = f"{KEYCLOAK_URL}/protocol/openid-connect/certs"

# Internal services
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:7000")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:7001")


# Auth helpers (Keycloak JWT)
def get_jwks():
    return requests.get(JWKS_URL, timeout=HTTP_TIMEOUT).json()

# Decode and verify JWT token
def decode_token(token: str):
    jwks = get_jwks()
    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        options={
            "verify_aud": False,
            "verify_iss": False
        }
    )

# Check and return decoded token for any authenticated user
def require_user():

    auth = request.headers.get("Authorization")
    if not auth:
        return None, ({"error": "Missing Authorization"}, 401)

    parts = auth.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, ({"error": "Invalid Authorization format"}, 401)

    token = parts[1]
    try:
        decoded = decode_token(token)
        return decoded, None
    except Exception as e:
        return None, ({"error": "Invalid token", "details": str(e)}, 401)

# Check if authenticated user is a seller
def ensure_seller(decoded):
    roles = decoded.get("realm_access", {}).get("roles", [])
    return "seller" in [r.lower() for r in roles]


# ORM model
class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String)
    seller_id = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Routes: Products 
@app.route("/")
def home():
    # List all products
    products = Product.query.order_by(Product.created_at.desc()).all()

    # Build response
    resp = make_response(jsonify({
        "message": "Welcome to AlpStore!",
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": float(p.price),
                "category": p.category,
                "stock": p.stock,
                "image_url": p.image_url
            } for p in products
        ]
    }), 200)

    # Add backend ID header for testing
    resp.headers["X-Backend-ID"] = socket.gethostname()
    return resp

# Routes: Seller dashboard
@app.route("/stocks")
def stocks():
    decoded, err = require_user()
    if err:
        return err

    if not ensure_seller(decoded):
        return {"error": "Seller only"}, 403

    seller_id = decoded.get("sub")
    products = Product.query.filter_by(seller_id=seller_id).order_by(Product.created_at.desc()).all()

    return {
        "message": "Seller dashboard",
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": float(p.price),
                "category": p.category,
                "stock": p.stock,
                "image_url": p.image_url,
                "created_at": p.created_at.isoformat()
            } for p in products
        ]
    }, 200

# Image upload route
@app.route("/upload-image", methods=["POST"])
def upload_image():
    if "file" not in request.files:
        return {"error": "No file uploaded"}, 400

    file = request.files["file"]
    filename = file.filename

    # Save file in upload folder
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(save_path)

    public_url = f"/static/uploads/{filename}"
    return {"url": public_url}, 200

# Send uploaded images
@app.route("/static/uploads/<path:filename>")
def serve_image(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Add new product
@app.route("/add-product", methods=["POST"])
def add_product():
    decoded, err = require_user()
    if err:
        return err

    if not ensure_seller(decoded):
        return {"error": "Seller only"}, 403

    seller_id = decoded.get("sub")
    data = request.get_json(silent=True) or {}

    p = Product(
        name=data.get("name"),
        description=data.get("description"),
        price=data.get("price"),
        category=data.get("category"),
        stock=data.get("stock"),
        image_url=data.get("imageUrl"),
        seller_id=seller_id,
    )

    db.session.add(p)
    db.session.commit()

    return {"message": "Product added", "id": p.id}, 200



# Routes: Orders (proxy to order-service)
@app.route("/orders", methods=["POST"])
def create_order_proxy():
    decoded, err = require_user()
    if err:
        return err

    # Extract order data
    user_id = decoded.get("sub")
    data = request.get_json(silent=True) or {}
    currency = (data.get("currency") or "ron").lower()
    items = data.get("items") or []

    if not items:
        return {"error": "items required"}, 400

    # normalize
    try:
        norm = [(int(it["product_id"]), int(it["qty"])) for it in items]
    except Exception:
        return {"error": "items must be [{product_id:int, qty:int}, ...]"}, 400

    for pid, qty in norm:
        if qty <= 0:
            return {"error": "qty must be > 0"}, 400

    # Fetch products and validate stock
    pids = [pid for pid, _ in norm]
    products = Product.query.filter(Product.id.in_(pids)).all()
    by_id = {p.id: p for p in products}
    
    # Check all products exist
    if len(by_id) != len(set(pids)):
        return {"error": "One or more products not found"}, 404

    # Check stock and calculate total
    total_bani = 0
    for pid, qty in norm:
        p = by_id[pid]
        if p.stock < qty:
            return {"error": f"Insufficient stock for '{p.name}' (have {p.stock}, need {qty})"}, 409
        total_bani += int(float(p.price) * 100) * qty

    r = requests.post(
        f"{ORDER_SERVICE_URL}/orders",
        json={
            "user_id": user_id,
            "currency": currency,
            "total_amount": total_bani,
            "items": [{"product_id": pid, "qty": qty} for pid, qty in norm],
        },
        timeout=HTTP_TIMEOUT,
    )
    return (r.json(), r.status_code)


# Get order details
@app.route("/orders/<int:order_id>", methods=["GET"])
def get_order_proxy(order_id):
    decoded, err = require_user()
    if err:
        return err

    r = requests.get(f"{ORDER_SERVICE_URL}/orders/{order_id}", timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        return (r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {"error": r.text}, r.status_code)

    order = r.json()

    user_id = decoded.get("sub")
    if order.get("user_id") != user_id and not ensure_seller(decoded):
        return {"error": "Forbidden"}, 403

    return (order, 200)

# Set Stripe session ID for order
@app.route("/orders/<int:order_id>/stripe-session", methods=["PATCH"])
def set_stripe_session_proxy(order_id):

    decoded, err = require_user()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    r = requests.patch(
        f"{ORDER_SERVICE_URL}/orders/{order_id}/stripe-session",
        json=data,
        timeout=HTTP_TIMEOUT
    )
    return (r.json(), r.status_code)


# Payments (proxy to payment-service)
@app.route("/pay", methods=["POST"])
def pay():
    
    # Body: { "order_id": 123 }
    # Returns: { "url": "https://checkout.stripe.com/..." }
    
    decoded, err = require_user()
    if err:
        return err

    user_id = decoded.get("sub")
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    if not order_id:
        return {"error": "order_id required"}, 400

    try:
        order_id = int(order_id)
    except Exception:
        return {"error": "order_id must be int"}, 400

    # Verify order exists and belongs to user
    r = requests.get(f"{ORDER_SERVICE_URL}/orders/{order_id}", timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        return {"error": "Order not found"}, 404
    order = r.json()

    if order.get("user_id") != user_id:
        return {"error": "Forbidden"}, 403

    if order.get("status") == "PAID":
        return {"error": "Order already paid"}, 409

    # Ask payment-service for checkout url
    r2 = requests.post(
        f"{PAYMENT_SERVICE_URL}/payments/checkout-session",
        json={"order_id": order_id},
        timeout=HTTP_TIMEOUT
    )

    # Forward response
    try:
        payload = r2.json()
    except Exception:
        payload = {"error": r2.text}

    return (payload, r2.status_code)

# Admin route to reset products
@app.route("/admin/reset-products", methods=["POST"])
def reset_products():
    decoded, err = require_user()
    if err:
        return err

    if not ensure_seller(decoded):
        return {"error": "Seller only"}, 403

    data = request.get_json(silent=True) or {}
    confirm = (data.get("confirm") or "").lower()
    if confirm != "yes":
        return {"error": "Pass {confirm:'yes'} to reset products"}, 400

    # Delete all products
    deleted = Product.query.delete()
    db.session.commit()

    return {"message": f"Deleted {deleted} products"}, 200



if __name__ == "__main__":

    ensure_alpstore_db_exists(PG_HOST, PG_USER, PG_PASSWORD)
    wait_for_db(app.config["SQLALCHEMY_DATABASE_URI"])

    with app.app_context():
        db.create_all()

    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", debug=DEBUG)
