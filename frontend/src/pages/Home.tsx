import { useEffect, useMemo, useState } from "react";
import ProductGrid from "../components/ProductGrid";
import CategorySidebar from "../components/CategorySidebar";
import { Product } from "../components/ProductCard";
import "./Home.css";

export default function Home({ isSeller }: { isSeller: boolean }) {
 
  const API = useMemo(() => "/api", []);
  // State for selected category and products
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const categories = ["Boots", "Backpacks", "Tents", "Jackets", "Pants"];

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      setLoading(true);
      setError(null);
      // Fetch products from API
      try {
        const res = await fetch(`${API}/`, { signal: controller.signal });

        const text = await res.text(); // read raw first (helps debugging)
        if (!res.ok) {
          throw new Error(`API error ${res.status}: ${text || res.statusText}`);
        }

        // Detect HTML responses (error case)
        if (text.trim().startsWith("<!doctype") || text.trim().startsWith("<html")) {
          throw new Error(`API returned HTML instead of JSON.\nFirst bytes: ${text.slice(0, 80)}`);
        }

        const data = JSON.parse(text);
        // Map raw data to Product objects
        const mapped: Product[] = (data.products ?? []).map((p: any) => ({
          id: Number(p.id),
          name: String(p.name),
          category: String(p.category),
          price: Number(p.price),
          stock: Number(p.stock ?? 0),
          image_url: p.image_url ?? null,
        }));

        setProducts(mapped);
      } catch (e: any) {
        if (e?.name === "AbortError") return;
        setProducts([]);
        setError(e?.message || "Failed to load products");
      } finally {
        setLoading(false);
      }
    }

    load();
    return () => controller.abort();
  }, [API]);

  // Filter products based on selected category
  const filteredProducts = useMemo(() => {
    return selectedCategory === null
      ? products
      : products.filter((p) => p.category === selectedCategory);
  }, [products, selectedCategory]);

  // Render the home page
  return (
    <div className="home-container">
      <div className="home-sidebar">
        <CategorySidebar
          categories={categories}
          selectedCategory={selectedCategory}
          onCategorySelect={setSelectedCategory}
        />
      </div>

      <div className="home-content">
        {loading ? (
          <h2>Loading products...</h2>
        ) : error ? (
          <>
            <h2>Could not load products</h2>
            <p style={{ opacity: 0.8, whiteSpace: "pre-wrap" }}>{error}</p>
            <p style={{ opacity: 0.7 }}>API used: {API}/</p>
          </>
        ) : (
          <>
            <h2>
              Showing {filteredProducts.length} products
              {selectedCategory && ` in "${selectedCategory}"`}
            </h2>

            <ProductGrid products={filteredProducts} />
          </>
        )}
      </div>
    </div>
  );
}
