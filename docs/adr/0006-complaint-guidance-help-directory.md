# ADR 0006: Governed Complaint Guidance and Verified Help Directory

## Status

Accepted

## Context

Phase 2.3 implements Product Specification FR-22 through FR-25. The platform provides guided legal awareness and support discovery; it is not a law firm, legal representative, or source of binding legal opinions. The existing `Complaint` record requires a sensitive narrative summary, so it is not suitable for browsing/selecting guidance. Existing `HelpResource` records lack source and freshness verification.

## Decisions

### Governed complaint guides

`ComplaintGuide` is a stable slug and lifecycle record. `ComplaintGuideVersion` stores immutable-after-review versions, jurisdiction, category, audience, dates, review/publication metadata, and an ordered JSONB sequence of typed steps. Drafts may be edited; a complete sequence must be submitted, reviewed, approved, and published. Required sections cover immediate safety, safety considerations, evidence preservation, reporting options, information to prepare, checklist, and escalation. Immediate safety is first and escalation is last. Publishing supersedes the previous published version. Admin lifecycle changes write structured audit events without storing guide prose or reviewer notes.

The student endpoints are `GET /api/v1/complaints/guides` and `GET /api/v1/complaints/guides/{slug}`. They return only active guides with published versions that have reviewer metadata, a current review date, and current effective dates. Filters cover category, jurisdiction, and audience; list pagination is bounded. Unpublished slugs return the same 404 as unknown slugs. This slice does not collect incident narratives or file complaints. Urgent safety instructions are editor-authored and available without AI or a long wizard.

### Help resource verification

`HelpResource` keeps its existing jurisdiction and contact fields and adds category, resource type, assistance type, contact method, source relationship, verifier/time, verification due date, and expiration. New resources start retired. They can be activated only through an authorized verification action against an active, current source configured for the same jurisdiction. Editing or retiring clears verification metadata. Student reads require active status, verifier and verification timestamp, an unexpired verification window and resource, and a current active source. Unverified, inactive, future-source, and expired resources are omitted rather than labelled verified.

`GET /api/v1/help` supports category, jurisdiction/location, assistance type, and bounded pagination. Student output includes contact and source citation/retrieval metadata, verification time, and a `verified_current` status; internal verifier IDs and source IDs are omitted.

### Authorization and audit

Guide drafts and review decisions require admin/reviewer roles; publishing, unpublishing, and guide archiving require admin/publisher roles. Resource creation and edits require admin/reviewer/publisher; verification and retirement require admin/publisher. All mutations create structured audit events. Audits record lifecycle, actor, resource, and limited classification/status metadata, never complaint narratives or guide prose.

## Migration and limitations

Migration `bc0d4f8a21e6` adds the guide/version tables and help-resource provenance/freshness fields without changing prior migrations. Existing help records are conservatively left unverified and have no source association, so they remain hidden from student results until governance verifies them. Guide text is administrative content: editorial accuracy still depends on qualified human review. This increment does not submit or persist incident reports, provide legal representation, predict outcomes, or issue legal verdicts.
