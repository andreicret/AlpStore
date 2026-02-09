import json
import os
import time
from datetime import datetime, timezone

import requests
import stripe
import pika
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

# Configuration from environment
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:7000")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "alpstore")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "alpstore123")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "order_payments")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:7001")
CURRENCY_DEFAULT = os.getenv("CURRENCY_DEFAULT", "ron")

stripe.api_key = STRIPE_SECRET_KEY

# Publish message to RabbitMQ with retries
def rabbitmq_publish(payload: dict) -> None:
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=creds,
        heartbeat=30,
        blocked_connection_timeout=30,
    )

    body = json.dumps(payload).encode("utf-8")
    last = None
    # Retry up to 20 times
    for attempt in range(1, 21):
        try:
            # Connect and publish
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

            ch.basic_publish(
                exchange="",
                routing_key=RABBITMQ_QUEUE,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # persistent
                    content_type="application/json",
                ),
            )
            conn.close()

            print(f"[rabbitmq] PUBLISHED queue={RABBITMQ_QUEUE} payload={payload}", flush=True)
            return
        except Exception as e:
            last = e
            print(f"[rabbitmq] publish attempt {attempt}/20 failed: {e}", flush=True)
            time.sleep(1)

    raise RuntimeError(f"Could not publish to RabbitMQ: {last}")


# Health check endpoint
@app.get("/health")
def health():
    return jsonify({
        "service": "payment-service",
        "stripe_key_set": bool(STRIPE_SECRET_KEY),
        "webhook_secret_set": bool(STRIPE_WEBHOOK_SECRET),
        "queue": RABBITMQ_QUEUE,
        "publish_queue_size": 0
    })

# Create a checkout session
@app.post("/payments/checkout-session")
def create_checkout_session():
    if not STRIPE_SECRET_KEY:
        abort(500, description="STRIPE_SECRET_KEY missing")
    # Parse input
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    if not order_id:
        abort(400, description="order_id required")

    # Load order
    r = requests.get(f"{ORDER_SERVICE_URL}/orders/{int(order_id)}", timeout=8)
    if r.status_code != 200:
        abort(r.status_code, description=f"order-service error: {r.text}")
    order = r.json()

    if order.get("status") == "PAID":
        abort(409, description="Order already paid")

    amount = int(order["total_amount"])
    currency = (order.get("currency") or CURRENCY_DEFAULT).lower()

    success_url = f"{PUBLIC_BASE_URL}/success?order_id={order_id}"
    cancel_url = f"{PUBLIC_BASE_URL}/cancel?order_id={order_id}"

    # Create checkout session
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": currency,
                "product_data": {"name": f"AlpStore Order #{order_id}"},
                "unit_amount": amount,
            },
            "quantity": 1
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(order_id),
        metadata={"order_id": str(order_id)},
    )

    # Patch order with stripe_session_id
    try:
        requests.patch(
            f"{ORDER_SERVICE_URL}/orders/{int(order_id)}/stripe-session",
            json={"stripe_session_id": session.id},
            timeout=8
        )
    except Exception as e:
        print(f"[order-service] patch stripe-session failed: {e}", flush=True)

    print(f"[stripe] created checkout session id={session.id} order_id={order_id}", flush=True)
    return jsonify({"url": session.url, "stripe_session_id": session.id})

# Stripe webhook endpoint
@app.post("/webhooks/stripe")
def stripe_webhook():
    if not STRIPE_WEBHOOK_SECRET:
        abort(500, description="STRIPE_WEBHOOK_SECRET missing")

    payload = request.get_data(as_text=False)
    sig_header = request.headers.get("Stripe-Signature", "")
    # Verify signature
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print(f"[stripe] webhook signature verification failed: {e}", flush=True)
        return (f"Webhook signature verification failed: {e}", 400)

    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    print(f"[stripe] event type={etype}", flush=True)

    # We accept both checkout.session.completed and payment_intent.succeeded
    if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        session = obj
        # Try to extract order id
        order_id = (
            session.get("client_reference_id")
            or (session.get("metadata") or {}).get("order_id")
        )
        stripe_session_id = session.get("id")
        payment_intent = session.get("payment_intent")

        print(f"[stripe] session.id={stripe_session_id} client_reference_id={session.get('client_reference_id')} metadata={session.get('metadata')}", flush=True)

        if not order_id:
            print("[stripe] WARNING: no order_id found in session; not publishing", flush=True)
            return ("ok", 200)

        msg = {
            "event_type": "PAYMENT_SUCCEEDED",
            "order_id": int(order_id),
            "stripe_session_id": stripe_session_id,
            "stripe_payment_intent": payment_intent,
            "amount": session.get("amount_total"),
            "currency": session.get("currency"),
            "occurred_at": datetime.now(timezone.utc).isoformat()
        }
        rabbitmq_publish(msg)

    elif etype == "payment_intent.succeeded":
       # Acknowledge payment intent succeeded
        pi = obj
        print(f"[stripe] payment_intent.succeeded id={pi.get('id')}", flush=True)

    return ("ok", 200)

# Success page
@app.get("/success")
def success_page():
    return "Payment success (Stripe) - you can close this tab.", 200

# Cancel page - TBC
@app.get("/cancel")
def cancel_page():
    return "Payment canceled (Stripe) - you can close this tab.", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "7001"))
    app.run(host="0.0.0.0", port=port, debug=False)
