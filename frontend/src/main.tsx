import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import keycloak from "./keycloak";
import { CartProvider } from "./cart/CartContext";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root not found");

// Initialize Keycloak and then render the app
async function bootstrap() {
  try {
    const authenticated = await keycloak.init({
      onLoad: "check-sso",
      pkceMethod: "S256",
      checkLoginIframe: false,
    });

    console.log("Keycloak initialized, authenticated =", authenticated);
  } catch (e) {
    console.error("Keycloak init failed:", e);
  }

  // Render the React application
  createRoot(rootElement).render(
    <StrictMode>
      <CartProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </CartProvider>
    </StrictMode>
  );
}

bootstrap();
