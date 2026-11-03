import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "system" | "light" | "dark";
const key = "roraima-theme";
function readTheme(): Theme {
  try {
    const value = localStorage.getItem(key);
    if (value === "light" || value === "dark") return value;
  } catch { /* Storage may be unavailable. */ }
  return "system";
}
function apply(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#101c29" : "#12304a");
}
apply(readTheme());
const ThemeContext = createContext<{ theme: Theme; change: (theme: Theme) => void }>({ theme: "system", change: () => {} });
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    apply(theme);
    const media = matchMedia("(prefers-color-scheme: dark)");
    const update = () => apply(theme);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [theme]);
  const change = (value: Theme) => {
    apply(value);
    setTheme(value);
    try { localStorage.setItem(key, value); } catch { /* Keep the choice for this session. */ }
  };
  return <ThemeContext.Provider value={{ theme, change }}>{children}</ThemeContext.Provider>;
}
export function ThemeSelector() {
  const { theme, change } = useContext(ThemeContext);
  return <label className="theme-selector">Tema <select value={theme} onChange={event => change(event.target.value as Theme)}><option value="system">Sistema</option><option value="light">Claro</option><option value="dark">Oscuro</option></select></label>;
}
