export type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";
export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: React.ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}
