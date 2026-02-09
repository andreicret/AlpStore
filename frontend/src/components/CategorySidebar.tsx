import "./CategorySidebar.css";

// Props for CategorySidebar component
interface CategorySidebarProps {
  categories: string[];
  selectedCategory: string | null;
  onCategorySelect: (category: string | null) => void;
}

export default function CategorySidebar({
  categories,
  selectedCategory,
  onCategorySelect,
}: CategorySidebarProps) {
  return ( 
    // Sidebar container
    <div className="sidebar enhanced">
      <div className="sidebar-header">
        <h3>Categories</h3>
      </div>

    
      {/* "All Products" button */}
      <button
        onClick={() => onCategorySelect(null)}
        className={selectedCategory === null ? "sidebar-btn active" : "sidebar-btn"}
      >
        All Products
      </button>

      {/* Category buttons */}
      {categories.map((category) => (
        <button
          key={category}
          onClick={() => onCategorySelect(category)}
          className={selectedCategory === category ? "sidebar-btn active" : "sidebar-btn"}
        >
          {category}
        </button>
      ))}
    </div>
  );
}
