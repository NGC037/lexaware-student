import { useCallback, useEffect, useMemo, useState } from "react";
import { ThemeContext, type ThemePreference } from "./theme-context";
const STORAGE_KEY = "lexaware-theme";

function readPreference(): ThemePreference {
  try { const value = localStorage.getItem(STORAGE_KEY); return value === "light" || value === "dark" ? value : "system"; }
  catch { return "system"; }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, updatePreference] = useState<ThemePreference>(readPreference);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false);

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return;
    const update = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  const setPreference = useCallback((value: ThemePreference) => {
    updatePreference(value);
    try { if (value === "system") localStorage.removeItem(STORAGE_KEY); else localStorage.setItem(STORAGE_KEY, value); }
    catch { /* Apply the preference for this session when storage is unavailable. */ }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = preference === "system" ? (systemDark ? "dark" : "light") : preference;
    document.documentElement.style.colorScheme = document.documentElement.dataset.theme;
  }, [preference, systemDark]);

  const value = useMemo(() => ({ preference, setPreference }), [preference, setPreference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

