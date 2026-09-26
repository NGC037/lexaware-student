import { Link } from "react-router";
export function NotFoundPage() { return <section className="not-found page-container"><p className="eyebrow">Page not found</p><h1>This page is not available.</h1><p>The address may have changed. Return to the LexAware Student home page to explore what is available.</p><Link className="button button--primary" to="/">Go to home</Link></section>; }
