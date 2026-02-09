import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useCart } from "../cart/CartContext";

type Order = {
  id: number;
  status: string;
  total_amount: number;
  currency: string;
};

// Check if a string looks like HTML
function isHtml(s: string) {
  const t = s.trim().toLowerCase();
  return t.startsWith("<!doctype") || t.startsWith("<html") || t.startsWith("<");
}

// Fetch order details from the API
async function fetchOrder(API: string, token: string, orderId: number): Promise<Order> {
  const r = await fetch(`${API}/orders/${orderId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const text = await r.text();

  if (isHtml(text)) {
    throw new Error(`API returned HTML instead of JSON.\nFirst bytes: ${text.slice(0, 120)}`);
  }

  // Parse JSON response
  let data: any;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }

  if (!r.ok) throw new Error(data?.error || data?.details || data?.raw || `HTTP ${r.status}`);
  return data as Order;
}

export default function SuccessPage({
  token,
  authenticated,
  onLogin,
}: {
  token: string | null;
  authenticated: boolean;
  onLogin: () => void;
}) {
  // Get order_id from URL parameters
  const [params] = useSearchParams();
  const orderId = Number(params.get("order_id") || 0);

  const { clear } = useCart();


  const clearRef = useRef(clear);
  useEffect(() => {
    clearRef.current = clear;
  }, [clear]);

  // Prepare API base URL
  const API = useMemo(() => {
    const raw = (import.meta.env.VITE_BACKEND_URL || "/api").toString().trim();
    if (raw.startsWith("http")) return raw.replace(/\/$/, "");
    return (raw.startsWith("/") ? raw : `/${raw}`).replace(/\/$/, "");
  }, []);

  const [order, setOrder] = useState<Order | null>(null);
  const [status, setStatus] = useState("Loading...");
  const [err, setErr] = useState("");

  // Keep latest token in ref for polling
  const tokenRef = useRef<string>("");
  useEffect(() => {
    tokenRef.current = token || localStorage.getItem("kc_token") || "";
  }, [token]);

  const doneRef = useRef(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    // Reset state for this order
    doneRef.current = false;
    if (timerRef.current) window.clearTimeout(timerRef.current);

    setErr("");
    setOrder(null);
    setStatus("Loading...");

    // Validate orderId
    if (!orderId) {
      setErr("Missing order_id in URL.");
      setStatus("Missing order_id");
      return;
    }

    if (!authenticated) {
      setStatus("Not authenticated");
      return;
    }

    let delay = 1200;

    const schedule = (ms: number) => {
      timerRef.current = window.setTimeout(poll, ms);
    };
    
    // Polling function to check order status
    const poll = async () => {
      if (doneRef.current) return;

      const t = tokenRef.current;
      if (!t) {
        // Wait for token after redirect/login
        schedule(600);
        return;
      }

      try {
        const o = await fetchOrder(API, t, orderId);
        if (doneRef.current) return;

        setOrder(o);
        setStatus(o.status);

        if (o.status === "PAID") {
          doneRef.current = true;
          clearRef.current(); 
          return;
        }

        if (o.status === "FAILED" || o.status === "CANCELED") {
          doneRef.current = true;
          return;
        }
        // Increase delay for next poll
        delay = Math.min(3000, Math.floor(delay * 1.15));
        schedule(delay);
      } catch (e: any) {
       
        setErr(e?.message || String(e));
        schedule(1500);
      }
    };

    poll();

    return () => {
      doneRef.current = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [orderId, authenticated, API]); 

  // Render different states based on order and authentication status
  if (!orderId) {
    return (
      <div style={{ maxWidth: 700, margin: "0 auto", padding: 16 }}>
        <h2>Payment Result</h2>
        <p style={{ color: "red" }}>Missing order_id.</p>
        <Link to="/">Back home</Link>
      </div>
    );
  }
  // Prompt login if not authenticated
  if (!authenticated) {
    return (
      <div style={{ maxWidth: 700, margin: "0 auto", padding: 16 }}>
        <h2>Payment Result</h2>
        <p>You must login to see your order status.</p>
        <button onClick={onLogin}>Login</button>
      </div>
    );
  }
  // Display order details and status
  return (
    <div style={{ maxWidth: 700, margin: "0 auto", padding: 16 }}>
      <h2>Payment Result</h2>

      {err && <p style={{ color: "red", whiteSpace: "pre-wrap" }}>{err}</p>}

      {!order ? (
        <p>Loading order #{orderId}...</p>
      ) : (
        <>
          <p>
            <b>Order:</b> #{order.id}
          </p>
          <p>
            <b>Status:</b> {status}
          </p>
          <p>
            <b>Total:</b> {(order.total_amount / 100).toFixed(2)}{" "}
            {String(order.currency).toUpperCase()}
          </p>

          {order.status === "PAID" ? (
            <p style={{ color: "green" }}>Payment confirmed. Thank you!</p>
          ) : ["FAILED", "CANCELED"].includes(order.status) ? (
            <p style={{ color: "red" }}>Payment not completed ({order.status}).</p>
          ) : (
            <p>Waiting for confirmation… (polling)</p>
          )}
        </>
      )}

      <div style={{ marginTop: 16, display: "flex", gap: 12 }}>
        <Link to="/">Back to shop</Link>
        <Link to="/cart">Go to cart</Link>
      </div>
    </div>
  );
}
