import { Brand } from "../components/Brand";

export function SiteFooter() {
  return <footer className="site-footer"><div className="page-container site-footer__top"><div><Brand /><p className="site-footer__summary">Clear information for the questions that matter to student life.</p></div><div className="site-footer__boundary"><strong>Awareness, not legal advice.</strong><p>LexAware helps you understand information and consider next steps. It does not replace a qualified professional.</p></div></div><div className="page-container site-footer__bottom"><span>© {new Date().getFullYear()} LexAware Student</span><span>Built around clarity, privacy, and care.</span></div></footer>;
}
