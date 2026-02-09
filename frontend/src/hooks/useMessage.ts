import { useEffect, useMemo, useState } from "react";

// Custom hook to fetch a message from the backend API
export function useMessage() {
  const [message, setMessage] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);

  const API = useMemo(() => {
    const raw = (import.meta.env.VITE_BACKEND_URL || "/api").replace(/\/$/, "");
    return raw || "/api";
  }, []);

  // Fetch the message when the component mounts
  useEffect(() => {
    fetch(`${API}/`)
      .then(async (res) => {
        const text = await res.text();
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
        if (text.trim().startsWith("<")) throw new Error("API returned HTML, not JSON");
        return JSON.parse(text);
      })
      .then((data) => setMessage(String(data.message ?? "")))
      .catch((e) => setMessage(`Error: ${e?.message || String(e)}`))
      .finally(() => setLoading(false));
  }, [API]);

  return { message, loading };
}
