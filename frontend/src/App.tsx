import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import SellerPage from "./pages/SellerPage";
import CartPage from "./pages/Cart";
import { useAuth } from "./hooks/useAuth";
import SuccessPage from "./pages/Success";


const App = () => {
  const { token, username, roles, login, logout } = useAuth();
  const isSeller = roles.includes("seller");
  // Main application layout with routing
  return (
    <>
      <Navbar
        username={username ?? ""}
        authenticated={!!token}
        roles={roles}
        onLogin={login}
        onLogout={logout}
      />
      
      <div style={{ paddingTop: "90px" }}>
        <Routes>
          <Route path="/" element={<Home isSeller={isSeller} />} />

          <Route
            path="/stocks"
            element={isSeller ? <SellerPage /> : <Home isSeller={false} />}
          />

          {/* Cart + Checkout */}
          <Route
            path="/cart"
            element={<CartPage token={token} authenticated={!!token} onLogin={login} />}
          />
          <Route
            path="/success"
            element={<SuccessPage token={token} authenticated={!!token} onLogin={login} />}
          />

        </Routes>
      </div>
    </>
  );
};

export default App;
