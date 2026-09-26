import { useEffect, useRef } from "react";

export function DocumentDeleteDialog({ filename, busy, onCancel, onConfirm }: {
  filename: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    cancelRef.current?.focus();
    return () => {
      if (!dialog.open) return;
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    };
  }, []);

  return <dialog ref={dialogRef} className="document-delete-dialog" aria-labelledby="document-delete-title" onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}>
    <p className="eyebrow">Remove from your private vault</p>
    <h2 id="document-delete-title">Delete this document?</h2>
    <p><strong>{filename}</strong> and its report will be deleted from your account. This action cannot be undone.</p>
    <div className="document-delete-dialog__actions">
      <button ref={cancelRef} className="button button--outline" type="button" disabled={busy} onClick={onCancel}>Keep document</button>
      <button className="button button--danger" type="button" disabled={busy} onClick={onConfirm}>{busy ? "Deleting…" : "Delete document"}</button>
    </div>
  </dialog>;
}
