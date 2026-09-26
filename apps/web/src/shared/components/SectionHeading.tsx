export function SectionHeading({ eyebrow, title, titleId, children, centered = false }: { eyebrow: string; title: string; titleId?: string; children: React.ReactNode; centered?: boolean }) {
  return <div className={`section-heading${centered ? " section-heading--centered" : ""}`}><p className="eyebrow">{eyebrow}</p><h2 id={titleId}>{title}</h2><p>{children}</p></div>;
}
