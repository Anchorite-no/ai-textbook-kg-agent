/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 表面
        "surface-app": "var(--surface-app)",
        "surface-card": "var(--surface-card)",
        "surface-input": "var(--surface-input)",
        "surface-muted": "var(--surface-muted)",
        "surface-overlay": "var(--surface-overlay)",
        // 文本
        "text-strong": "var(--text-strong)",
        "text-default": "var(--text-default)",
        "text-muted": "var(--text-muted)",
        "text-inverse": "var(--text-inverse)",
        // 主色
        "brand-50": "var(--brand-50)",
        "brand-100": "var(--brand-100)",
        "brand-500": "var(--brand-500)",
        "brand-600": "var(--brand-600)",
        "brand-700": "var(--brand-700)",
        // 状态
        "status-pending": "var(--status-pending)",
        "status-running": "var(--status-running)",
        "status-success": "var(--status-success)",
        "status-warning": "var(--status-warning)",
        "status-error": "var(--status-error)",
        // 教材染色
        "book-1": "var(--book-1)",
        "book-2": "var(--book-2)",
        "book-3": "var(--book-3)",
        "book-4": "var(--book-4)",
        "book-5": "var(--book-5)",
        "book-6": "var(--book-6)",
        "book-7": "var(--book-7)",
        "book-8": "var(--book-8)",
        // 边框
        "border-soft": "var(--border-soft)",
        "border-strong": "var(--border-strong)"
      },
      fontFamily: {
        sans: "var(--font-sans)",
        mono: "var(--font-mono)"
      },
      fontSize: {
        meta: ["12px", { lineHeight: "16px" }],
        body: ["13px", { lineHeight: "20px" }],
        h2: ["15px", { lineHeight: "22px", fontWeight: "600" }],
        display: ["20px", { lineHeight: "28px", fontWeight: "600" }]
      },
      borderRadius: {
        control: "var(--radius-control)",
        card: "var(--radius-card)",
        pill: "var(--radius-pill)"
      },
      boxShadow: {
        card: "var(--shadow-card)",
        overlay: "var(--shadow-overlay)",
        modal: "var(--shadow-modal)",
        focus: "var(--focus-ring)"
      },
      transitionTimingFunction: {
        standard: "cubic-bezier(0.4, 0, 0.2, 1)",
        decelerate: "cubic-bezier(0, 0, 0.2, 1)",
        accelerate: "cubic-bezier(0.4, 0, 1, 1)",
        emphasized: "cubic-bezier(0.76, 0, 0.24, 1)"
      },
      transitionDuration: {
        micro: "150ms",
        fast: "200ms",
        base: "240ms",
        slow: "320ms",
        graph: "100ms"
      },
      zIndex: {
        sticky: "10",
        dropdown: "100",
        drawer: "200",
        modal: "300",
        toast: "400",
        tooltip: "500"
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" }
        },
        "fade-in-up": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" }
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.96)" },
          to: { opacity: "1", transform: "scale(1)" }
        },
        breathing: {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.04)" }
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" }
        }
      },
      animation: {
        "fade-in": "fade-in 160ms cubic-bezier(0, 0, 0.2, 1)",
        "fade-in-up": "fade-in-up 160ms cubic-bezier(0, 0, 0.2, 1)",
        "scale-in": "scale-in 200ms cubic-bezier(0.4, 0, 0.2, 1)",
        breathing: "breathing 3.6s ease-in-out infinite",
        shimmer: "shimmer 1.6s linear infinite"
      }
    }
  },
  plugins: []
};
