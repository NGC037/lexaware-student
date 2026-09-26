export function StatePanel({ kind = "empty", title, children }: {
  kind?: "empty" | "error" | "info"; title: string; children: React.ReactNode;
}) {
  return <section className={`state-panel state-panel--${kind}`} role={kind === "error" ? "alert" : "status"}>
    <h2>{title}</h2><p>{children}</p>
  </section>;
}
