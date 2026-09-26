import { Outlet } from "react-router";
import { Brand } from "../components/Brand";
import { ThemeControl } from "../theme/ThemeControl";

export function PublicAuthLayout() {
  return <div className="auth-site"><header className="auth-site__header page-container"><Brand /><ThemeControl /></header><main className="auth-site__main"><Outlet /></main><footer className="auth-site__footer page-container"><span>LexAware Student</span><span>Legal awareness and guided support, not legal advice.</span></footer></div>;
}
