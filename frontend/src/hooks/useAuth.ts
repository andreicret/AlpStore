import { useEffect, useRef, useState } from "react";
import keycloak from "../keycloak";

// Helper to extract and lowercase roles from token
function lowerRoles(tokenParsed: any): string[] {
  return (tokenParsed?.realm_access?.roles ?? []).map((r: string) => String(r).toLowerCase());
}

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [roles, setRoles] = useState<string[]>([]);

  // Keep last values to avoid useless re-renders
  const lastTokenRef = useRef<string | null>(null);
  const lastUserRef = useRef<string | null>(null);
  const lastRolesRef = useRef<string>("");

  const syncFromKeycloak = () => {
    const t = keycloak.token ?? null;

    if (!t) {
      // logged out / not authenticated
      if (lastTokenRef.current !== null) {
        lastTokenRef.current = null;
        lastUserRef.current = null;
        lastRolesRef.current = "";
        localStorage.removeItem("kc_token");
        setToken(null);
        setUsername(null);
        setRoles([]);
      }
      return;
    }

    const parsed: any = keycloak.tokenParsed ?? {};
    const user = parsed.preferred_username ?? null;
    const r = lowerRoles(parsed);
    const rKey = r.join("|");

    // Update only if something changed
    if (lastTokenRef.current !== t) {
      lastTokenRef.current = t;
      localStorage.setItem("kc_token", t);
      setToken(t);
    }

    if (lastUserRef.current !== user) {
      lastUserRef.current = user;
      setUsername(user);
    }

    if (lastRolesRef.current !== rKey) {
      lastRolesRef.current = rKey;
      setRoles(r);
    }
  };

  // Initial sync (after keycloak.init already happened in main.tsx)
  useEffect(() => {
    syncFromKeycloak();

    // Hook into Keycloak events (best-effort; not all builds expose all handlers)
    (keycloak as any).onAuthSuccess = syncFromKeycloak;
    (keycloak as any).onAuthRefreshSuccess = syncFromKeycloak;
    (keycloak as any).onAuthLogout = syncFromKeycloak;
    (keycloak as any).onTokenExpired = async () => {
      try {
        await keycloak.updateToken(30);
      } finally {
        syncFromKeycloak();
      }
    };

    return () => {
      (keycloak as any).onAuthSuccess = undefined;
      (keycloak as any).onAuthRefreshSuccess = undefined;
      (keycloak as any).onAuthLogout = undefined;
      (keycloak as any).onTokenExpired = undefined;
    };
  
  }, []);

  // Refresh token periodically
  useEffect(() => {
    const interval = window.setInterval(async () => {
      if (!keycloak.authenticated) return;
      try {
        const refreshed = await keycloak.updateToken(30);
        if (refreshed) syncFromKeycloak(); // will only setState if token actually changed
      } catch {
        // 
      }
    }, 20000);

    return () => window.clearInterval(interval);
    
  }, []);

  return {
    token,
    username,
    roles,
    login: () => keycloak.login(),
    logout: () => keycloak.logout({ redirectUri: window.location.origin }),
  };
}
