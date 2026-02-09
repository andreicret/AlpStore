import React, { createContext, useContext, useMemo, useState } from "react";

// Define the shape of a cart item
export type CartItem = {
  id: number;
  name: string;
  price: number;
  image_url?: string;
  qty: number;
};

// Define the context type
type CartContextType = {
  items: CartItem[];
  addItem: (p: Omit<CartItem, "qty">) => void;
  removeItem: (id: number) => void;
  setQty: (id: number, qty: number) => void;
  clear: () => void;
};

const CartContext = createContext<CartContextType | null>(null);

// CartProvider component to wrap around parts of the app that need cart access
export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  
  const api = useMemo<CartContextType>(() => ({
    items,
    addItem: (p) => {
      // Check if the item already exists in the cart
      setItems(prev => {
        const idx = prev.findIndex(x => x.id === p.id);
        if (idx >= 0) {
          const copy = [...prev];
          copy[idx] = { ...copy[idx], qty: copy[idx].qty + 1 };
          return copy;
        }
        return [...prev, { ...p, qty: 1 }];
      });
    }, 
    removeItem: (id) => setItems(prev => prev.filter(x => x.id !== id)),
    setQty: (id, qty) =>
      setItems(prev => prev.map(x => x.id === id ? { ...x, qty: Math.max(1, qty) } : x)),
    clear: () => setItems([]),
  }), [items]);
  // Provide the cart context to children components
  return (
    <CartContext.Provider value={api}>
      {children}
    </CartContext.Provider>
  );
}
// Custom hook to use the cart context
export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside CartProvider");
  return ctx;
}
