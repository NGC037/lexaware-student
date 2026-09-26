import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme, type ThemePreference } from "../../app/theme/theme-context";

export function ThemeControl() {
  const { preference, setPreference } = useTheme();
  return <label className="theme-control"><span className="visually-hidden">Color theme</span><Sun aria-hidden="true" className="theme-control__icon" size={16} /><select aria-label="Color theme" onChange={(event) => setPreference(event.target.value as ThemePreference)} value={preference}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select><Moon aria-hidden="true" className="theme-control__dark-icon" size={16} /><Monitor aria-hidden="true" className="visually-hidden" /></label>;
}
