from app.db.models import Document, DocumentStatus


class InvalidDocumentTransition(ValueError):
    """Raised when a document attempts an unsupported lifecycle transition."""


_ALLOWED_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.UPLOADED: frozenset({DocumentStatus.VALIDATING, DocumentStatus.VALIDATED}),
    DocumentStatus.VALIDATING: frozenset(
        {DocumentStatus.VALIDATED, DocumentStatus.UNSUPPORTED, DocumentStatus.FAILED}
    ),
    DocumentStatus.VALIDATED: frozenset({DocumentStatus.PROCESSING, DocumentStatus.FAILED}),
    DocumentStatus.PROCESSING: frozenset(
        {
            DocumentStatus.VALIDATED,
            DocumentStatus.EXTRACTED,
            DocumentStatus.UNSUPPORTED,
            DocumentStatus.COMPLETED,
            DocumentStatus.FAILED,
        }
    ),
    DocumentStatus.EXTRACTED: frozenset(
        {DocumentStatus.ANALYZING, DocumentStatus.UNSUPPORTED, DocumentStatus.FAILED}
    ),
    DocumentStatus.ANALYZING: frozenset(
        {DocumentStatus.COMPLETED, DocumentStatus.UNSUPPORTED, DocumentStatus.FAILED}
    ),
    DocumentStatus.COMPLETED: frozenset(),
    DocumentStatus.READY: frozenset(),
    DocumentStatus.FAILED: frozenset({DocumentStatus.VALIDATED}),
    DocumentStatus.UNSUPPORTED: frozenset(),
    DocumentStatus.DELETED: frozenset(),
}


def transition_document(document: Document, target: DocumentStatus) -> None:
    current = document.status
    if target == current:
        return
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidDocumentTransition(
            f"Cannot transition document from {current.value} to {target.value}."
        )
    document.status = target
