import { useState } from "react";
import { Menu, X } from "lucide-react";
import { Brand } from "../components/Brand";
import { ThemeControl } from "../theme/ThemeControl";

const links = [{ href: "#how-it-works", label: "How it works" }, { href: "#what-you-can-do", label: "Explore support" }, { href: "#our-approach", label: "Our approach" }];
export function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);
  return <header className="site-header"><div className="site-header__inner page-container">
    <Brand onNavigate={closeMenu} />
    <nav aria-label="Main navigation" className={`primary-nav${menuOpen ? " primary-nav--open" : ""}`}>
      {links.map((link) => <a key={link.href} href={link.href} onClick={closeMenu}>{link.label}</a>)}
      <a className="button button--small button--outline nav-cta" href="#how-it-works" onClick={closeMenu}>Get started</a>
    </nav>
    <div className="site-header__actions"><ThemeControl /><button aria-controls="mobile-navigation" aria-expanded={menuOpen} aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"} className="menu-toggle" onClick={() => setMenuOpen((open) => !open)} type="button">{menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}</button></div>
  </div><div className={`mobile-menu${menuOpen ? " mobile-menu--open" : ""}`} id="mobile-navigation" hidden={!menuOpen}><nav aria-label="Mobile navigation" className="page-container">{links.map((link) => <a key={link.href} href={link.href} onClick={closeMenu}>{link.label}</a>)}<a href="#how-it-works" onClick={closeMenu}>Get started</a></nav></div></header>;
}
