import "./Navbar.css";
import { Link, useNavigate } from "react-router-dom";
import { useCart } from "../cart/CartContext";

// Props for Navbar component
interface NavbarProps {
  username: string | null;
  authenticated: boolean;
  roles?: string[];
  onLogin: () => void;
  onLogout: () => void;
}

export default function Navbar({
  username,
  authenticated,
  roles = [],
  onLogin,
  onLogout,
}: NavbarProps) { 
  const navigate = useNavigate();
  const isSeller = roles.includes("seller");
  // Get cart items from context
  const { items } = useCart();
  const cartCount = items.reduce((s, it) => s + it.qty, 0);

  const handleSettingsClick = () => {
    if (isSeller) navigate("/stocks");
  };

  const handleCartClick = () => {
    navigate("/cart");
  };
  
  return (
    <nav className="nav">
      <div className="nav-left">
        <Link to="/" className="nav-home-link">
          <img src="/alpstore.png" className="nav-logo" />
        </Link>

        <Link to="/" className="nav-title nav-home-link">
          AlpStore
        </Link>
      </div>

      <div className="nav-right">
        {!authenticated && (
          <button className="nav-login-btn" onClick={onLogin}>
            Login
          </button>
        )}

        {authenticated && (
          <>
            <span className="nav-user">
              Welcome, <strong>{username}</strong>
            </span>
            <button className="nav-logout-btn" onClick={onLogout}>
              Logout
            </button>
          </>
        )}
        
        {/* card or settings depending on role */} 
        {!isSeller ? (
          <button className="nav-cart-btn" onClick={handleCartClick} title="Cart">
            🛒 {cartCount > 0 ? `(${cartCount})` : ""}
          </button>
        ) : (
          <button className="nav-cart-btn" onClick={handleSettingsClick} title="Seller settings">
            ⚙️
          </button>
        )}
      </div>
    </nav>
  );
}
