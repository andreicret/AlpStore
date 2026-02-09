import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import "./SellerPage.css";

const API_BASE = import.meta.env.VITE_BACKEND_URL;

// Form state interface
interface ProductForm {
  name: string;
  description: string;
  price: number;
  category: string;
  stock: number;
  imageUrl: string;
}

export default function SellerPage() {
  const { token } = useAuth();

  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("");

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const categories = ["Boots", "Backpacks", "Tents", "Jackets", "Pants"];
  // Form state
  const [form, setForm] = useState<ProductForm>({
    name: "",
    description: "",
    price: 0,
    category: "Boots",
    stock: 1,
    imageUrl: "",
  });

// Seller info fetch
  useEffect(() => {
    if (!token) return;

    fetch(`${API_BASE}/stocks`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => res.json())
      .then((data) => setMessage(data.message ?? "Seller dashboard"))
      .catch(() => setMessage("Failed to load seller info"));
  }, [token]);

// Image upload
  async function uploadImage(): Promise<string | null> {
    if (!imageFile) return null;

    const formData = new FormData();
    formData.append("file", imageFile);

    const res = await fetch(`${API_BASE}/upload-image`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) return null;

    const data = await res.json();
    return data.url; // ex: /static/uploads/img.jpg
  }

  // Submit new product
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!token) {
      setStatus("You must be logged in");
      return;
    }

    setStatus("Submitting...");

    let imageUrl = form.imageUrl;

    if (imageFile) {
      const uploaded = await uploadImage();
      if (!uploaded) {
        setStatus("Image upload failed");
        return;
      }
      imageUrl = uploaded;
    }

    const res = await fetch(`${API_BASE}/add-product`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ ...form, imageUrl }),
    });

    const data = await res.json();

    if (!res.ok) {
      setStatus(data.error ?? "Failed to add product");
      return;
    }

    setStatus("Product added successfully!");
    setForm({
      name: "",
      description: "",
      price: 0,
      category: "Boots",
      stock: 1,
      imageUrl: "",
    });
    setImageFile(null);
    setImagePreview(null);
  }

 // UI render
  return (
    <div className="seller-container">
      <h1>Seller Dashboard</h1>
      <p>{message}</p>

      <h2>Add New Product</h2>

      <form className="product-form" onSubmit={handleSubmit}>
        <label>Product Name</label>
        <input
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          required
        />

        <label>Description</label>
        <textarea
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          required
        />

        <label>Price (€)</label>
        <input
          type="number"
          min="1"
          step="any"
          value={form.price}
          onChange={(e) => setForm({ ...form, price: Number(e.target.value) })}
          required
        />

        <label>Category</label>
        <select
          value={form.category}
          onChange={(e) => setForm({ ...form, category: e.target.value })}
        >
          {categories.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>

        <label>Stock</label>
        <input
          type="number"
          min="1"
          value={form.stock}
          onChange={(e) => setForm({ ...form, stock: Number(e.target.value) })}
        />

        <label>Upload Image</label>
        <input
          type="file"
          accept="image/*"
          onChange={(e) => {
            const file = e.target.files?.[0] || null;
            setImageFile(file);
            setImagePreview(file ? URL.createObjectURL(file) : null);
          }}
        />

        {imagePreview && (
          <img src={imagePreview} className="preview-img" alt="preview" />
        )}

        <button className="submit-btn" type="submit">
          Add Product
        </button>
      </form>

      {status && <p className="status-msg">{status}</p>}
    </div>
  );
}
