import json
import os
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request, abort
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    BigInteger,
    UniqueConstraint,
    ForeignKey,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError

import pika

# Configuration from environment
DB_HOST = os.getenv("PG_HOST", "postgres")
DB_PORT = int(os.getenv("PG_PORT", "5432"))
DB_NAME = os.getenv("PG_DB", "alpstore")
DB_USER = os.getenv("PG_USER", "keycloak")
DB_PASSWORD = os.getenv("PG_PASSWORD", "keycloak123")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "alpstore")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "alpstore123")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "order_payments")

ENABLE_CONSUMER = os.getenv("ENABLE_CONSUMER", "true").lower() in ("1", "true", "yes")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

# DB setup
Base = declarative_base()

# 
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(String(128), nullable=False)

    total_amount = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False, default="ron")

    status = Column(String(16), nullable=False, default="PENDING")  # PENDING/PAID/FAILED/CANCELED

    stripe_session_id = Column(String(255), nullable=True)
    stripe_payment_intent = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("stripe_session_id", name="uq_orders_stripe_session_id"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
    )


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    Base.metadata.create_all(bind=engine)



app = Flask(__name__)


# Health check for service and DB
@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    return jsonify(
        {
            "service": "order-service",
            "db_ok": db_ok,
            "consumer_enabled": ENABLE_CONSUMER,
            "queue": RABBITMQ_QUEUE,
        }
    )

# Create a new order
@app.post("/orders")
def create_order():
    
    # body:
    # {
    #   "user_id": "abc",
    #   "total_amount": 19900,
    #   "currency": "ron",
    #   "items": [{"product_id": 5, "qty": 2}, ...]
    # }
    
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    total_amount = data.get("total_amount")
    currency = (data.get("currency") or "ron").lower()
    items = data.get("items") or []

    if not user_id or total_amount is None:
        abort(400, description="Missing required fields: user_id, total_amount")

    if not items:
        abort(400, description="Missing required field: items")

    # Validate total_amount and items
    try:
        total_amount = int(total_amount)
        if total_amount <= 0:
            abort(400, description="total_amount must be > 0")
    except ValueError:
        abort(400, description="total_amount must be integer")

    norm_items = []
    try:
        for it in items:
            pid = int(it.get("product_id"))
            qty = int(it.get("qty"))
            if qty <= 0:
                abort(400, description="qty must be > 0")
            norm_items.append((pid, qty))
    except Exception:
        abort(400, description="Invalid items format. Expect: [{product_id:int, qty:int}, ...]")
    # Create order and items
    db = SessionLocal()
    try:
        order = Order(
            user_id=user_id,
            total_amount=total_amount,
            currency=currency,
            status="PENDING",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # store items
        for pid, qty in norm_items:
            db.add(OrderItem(order_id=order.id, product_id=pid, qty=qty))
        db.commit()

        return jsonify(order_to_dict(db, order)), 201
    finally:
        db.close()

# Get order by ID
@app.get("/orders/<int:order_id>")
def get_order(order_id: int):
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).one_or_none()
        if not order:
            abort(404, description="Order not found")
        return jsonify(order_to_dict(db, order))
    finally:
        db.close()

# Update order with Stripe session info
@app.patch("/orders/<int:order_id>/stripe-session")
def set_stripe_session(order_id: int):

    data = request.get_json(silent=True) or {}
    stripe_session_id = data.get("stripe_session_id")
    if not stripe_session_id:
        abort(400, description="stripe_session_id is required")

    stripe_payment_intent = data.get("stripe_payment_intent")

    
    db = SessionLocal()

    # Update order
    try:
        order = db.query(Order).filter(Order.id == order_id).one_or_none()
        if not order:
            abort(404, description="Order not found")

        if order.stripe_session_id == stripe_session_id:
            return jsonify(order_to_dict(db, order))

        if order.stripe_session_id and order.stripe_session_id != stripe_session_id:
            abort(409, description="Order already linked to a different stripe_session_id")
        # Set stripe ids
        order.stripe_session_id = stripe_session_id
        if stripe_payment_intent:
            order.stripe_payment_intent = stripe_payment_intent
        order.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return jsonify(order_to_dict(db, order))
    except IntegrityError:
        db.rollback()
        abort(409, description="stripe_session_id already used by another order")
    finally:
        db.close()


# Apply stock changes for an order
# Decrements stock for products in the order. If stock reaches 0, deletes the product.
# Uses row locks to be safe under concurrency.
def apply_stock_changes(db, order_id: int):
    
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    if not items:
        return

    # Apply stock changes
    for it in items:
        row = db.execute(
            text("SELECT id, stock FROM products WHERE id = :pid FOR UPDATE"),
            {"pid": it.product_id},
        ).mappings().first()

        if not row:
            raise ValueError(f"Product {it.product_id} not found")
        # Check stock
        stock = int(row["stock"])
        if stock < int(it.qty):
            raise ValueError(f"Insufficient stock for product {it.product_id}: have {stock}, need {it.qty}")

        new_stock = stock - int(it.qty)

        if new_stock == 0:
            db.execute(text("DELETE FROM products WHERE id = :pid"), {"pid": it.product_id})
        else:
            db.execute(
                text("UPDATE products SET stock = :s WHERE id = :pid"),
                {"s": new_stock, "pid": it.product_id},
            )


# RabbitMQ connection with retry that returns a BlockingConnection
def rabbitmq_connect_with_retry(max_wait_s: int = 60):
    deadline = time.time() + max_wait_s
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=creds,
        heartbeat=30,
        blocked_connection_timeout=30,
    )

    last_err = None
    # Retry loop
    while time.time() < deadline:
        try:
            return pika.BlockingConnection(params)
        except Exception as e:
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"Could not connect to RabbitMQ within {max_wait_s}s: {last_err}")

# Process payment event from RabbitMQ
# Expects PAYMENT_SUCCEEDED with order_id and optional stripe ids.
# Marks order as PAID and decrements stock atomically.
def process_payment_event(payload: dict):

    if payload.get("event_type") != "PAYMENT_SUCCEEDED":
        return
    # Extract order_id and stripe ids from payload
    order_id = payload.get("order_id")
    stripe_session_id = payload.get("stripe_session_id")
    stripe_payment_intent = payload.get("stripe_payment_intent")

    if not order_id:
        raise ValueError("Missing order_id in event")

    db = SessionLocal()
    try:
        # Fetch order
        order = db.query(Order).filter(Order.id == int(order_id)).one_or_none()
        if not order:
            return

        # Idempotency: don't apply stock twice
        if order.status == "PAID":
            return

        # Consistency check
        if order.stripe_session_id and stripe_session_id and order.stripe_session_id != stripe_session_id:
            raise ValueError("stripe_session_id mismatch for order")

        # Ensure stripe ids are set
        if stripe_session_id and not order.stripe_session_id:
            order.stripe_session_id = stripe_session_id
        if stripe_payment_intent:
            order.stripe_payment_intent = stripe_payment_intent

        # Atomic stock decrement + mark paid
        apply_stock_changes(db, order.id)

        order.status = "PAID"
        now = datetime.now(timezone.utc)
        order.paid_at = now
        order.updated_at = now

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def consumer_loop():
    while True:
        try:
            # Connect to RabbitMQ
            conn = rabbitmq_connect_with_retry(max_wait_s=120)
            ch = conn.channel()

            ch.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            ch.basic_qos(prefetch_count=1)

            # Message handler
            def on_message(channel, method, properties, body: bytes):
                try:
                    payload = json.loads(body.decode("utf-8"))
                    process_payment_event(payload)
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print(f"[consumer] error processing message: {e} payload={body!r}", flush=True)
                    # ack to avoid poison loop (you can switch to requeue if you want)
                    channel.basic_ack(delivery_tag=method.delivery_tag)
            # Start consuming
            ch.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=on_message, auto_ack=False)
            print(f"[consumer] listening on queue={RABBITMQ_QUEUE} host={RABBITMQ_HOST}:{RABBITMQ_PORT}", flush=True)
            ch.start_consuming()

        except Exception as e:
            print(f"[consumer] connection/consume error: {e}. retrying in 3s...", flush=True)
            time.sleep(3)

# Convert Order ORM object to dict
def order_to_dict(db, order: Order) -> dict:
    def dt(v):
        return v.isoformat() if v else None

    item_rows = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    items = [{"product_id": it.product_id, "qty": it.qty} for it in item_rows]

    return {
        "id": order.id,
        "user_id": order.user_id,
        "total_amount": int(order.total_amount),
        "currency": order.currency,
        "status": order.status,
        "stripe_session_id": order.stripe_session_id,
        "stripe_payment_intent": order.stripe_payment_intent,
        "items": items,
        "created_at": dt(order.created_at),
        "updated_at": dt(order.updated_at),
        "paid_at": dt(order.paid_at),
    }

# Wait for DB to be ready
def wait_for_db(max_wait_s: int = 60):
    deadline = time.time() + max_wait_s
    last_err = None
    while time.time() < deadline:
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return
        except OperationalError as e:
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"DB not ready after {max_wait_s}s: {last_err}")


if __name__ == "__main__":
    wait_for_db(max_wait_s=120)

    INIT_DB = os.getenv("INIT_DB", "false").lower() in ("1", "true", "yes")
    if INIT_DB:
        init_db()
    # Start consumer thread
    if ENABLE_CONSUMER:
        t = threading.Thread(target=consumer_loop, daemon=True)
        t.start()

    port = int(os.getenv("PORT", "7000"))
    app.run(host="0.0.0.0", port=port)
