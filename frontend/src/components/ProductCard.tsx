import "./ProductCard.css";
import { useCart } from "../cart/CartContext";

// Props for ProductCard component
export interface Product {
  id: number;
  name: string;
  category: string;
  price: number;
  stock: number;
  image_url?: string | null;
}

export default function ProductCard({ id, name, category, price, stock, image_url }: Product) {
  const { addItem } = useCart();

  // Always relative behind Traefik
  const API = "/api";

  // Determine the image source
  const imgSrc = image_url
    ? image_url.startsWith("http")
      ? image_url
      : `${API}${image_url}`
    : "/alpstore.png";

  const outOfStock = stock <= 0;

  // Render the product card
  return (
    <div className="product-card">
      <div className="product-image-wrapper">
        <img src={imgSrc} className="product-img" alt={name} />
      </div>

      <div className="product-info">
        <p className="product-category">{category.toUpperCase()}</p>
        <h3 className="product-title">{name}</h3>
        <p className="product-price">{price.toFixed(2)} RON</p>
        <p style={{ opacity: 0.8, marginTop: 6 }}>
          Stock: <b>{stock}</b>
        </p>
      </div>

      <button
        className="product-add-btn"
        disabled={outOfStock}
        onClick={() => addItem({ id, name, price, image_url: image_url ?? undefined })}
      >
        {outOfStock ? "Out of stock" : "Add to Cart"}
      </button>
    </div>
  );
}
