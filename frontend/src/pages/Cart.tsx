import { useMemo, useState } from "react";
import { useCart } from "../cart/CartContext";

const BACKEND = (import.meta.env.VITE_BACKEND_URL || "/api").replace(/\/$/, "");


// Helper function to make HTTP requests and parse JSON responses
async function httpJson(url: string, opts: RequestInit) {
  const r = await fetch(url, opts);
  const text = await r.text();
  let data: any;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }

  if (!r.ok) {
    throw new Error(data?.error || data?.details || data?.raw || `HTTP ${r.status}`);
  }
  return data;
}

export default function CartPage({
  token,
  authenticated,
  onLogin,
}: {
  token: string | null;
  authenticated: boolean;
  onLogin: () => void;
}) {
  const { items, setQty, removeItem, clear } = useCart();
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  // Calculate total amount
  const totalBani = useMemo(() => {
    return items.reduce((acc, it) => acc + Math.round(Number(it.price) * 100) * it.qty, 0);
  }, [items]);

  // Handle checkout process
  async function checkout() {
    if (!authenticated || !token) {
      onLogin();
      return;
    }

    if (items.length === 0) {
      setErr("Cart is empty.");
      return;
    }

    // Reset error and set loading state
    setErr("");
    setLoading(true);
    try {
      // 1) Create order (send items for stock decrement later)
      const order = await httpJson(`${BACKEND}/orders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          currency: "ron",
      items: items.map((it) => ({
            product_id: it.id,
            qty: it.qty,
          })),

          total_amount: totalBani,
        }),
      });

      // 2) Pay -> redirect to Stripe
      const pay = await httpJson(`${BACKEND}/pay`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ order_id: order.id }),
      });

      window.location.href = pay.url;
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }
  // Render the cart page
  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 16 }}>
      <h2>Cart</h2>

      {items.length === 0 ? (
        <p>Cart is empty.</p>
      ) : (
        <>
          {items.map((it) => (
            <div key={it.id} style={{ display: "flex", gap: 12, alignItems: "center", padding: "10px 0" }}>
              <div style={{ flex: 1 }}>
                <b>{it.name}</b>
                <div style={{ opacity: 0.8 }}>Price: {it.price.toFixed(2)} RON</div>
              </div>

              <input
                type="number"
                min={1}
                value={it.qty}
                onChange={(e) => setQty(it.id, Number(e.target.value))}
                style={{ width: 80 }}
              />

              <button onClick={() => removeItem(it.id)}>Remove</button>
            </div>
          ))}

          <hr />
          <p>
            <b>Total:</b> {(totalBani / 100).toFixed(2)} RON
          </p>

          {err && <p style={{ color: "red" }}>{err}</p>}

          <button disabled={loading} onClick={checkout}>
            {authenticated ? (loading ? "Redirecting..." : "Pay with Stripe") : "Login to Checkout"}
          </button>

          <button style={{ marginLeft: 12 }} onClick={clear} disabled={loading}>
            Clear cart
          </button>
        </>
      )}
    </div>
  );
}
