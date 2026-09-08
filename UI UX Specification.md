LexAware Student
UI/UX and Frontend Design Specification
Version: 1.0
Prepared by: Manus AI
Status: Build-ready design baseline
Product: LexAware Student — AI-Powered Legal Awareness and Assistance Platform for Students

Design promise: Make legal awareness feel clear, calm, trustworthy, and actionable.

1. Purpose and Design Direction
   This document defines the user experience, visual identity, interaction model, frontend architecture, design tokens, component system, motion strategy, accessibility requirements, and implementation standards for LexAware Student.

LexAware handles sensitive questions and private documents. The interface must therefore communicate trust without implying legal authority, clarity without oversimplification, and guidance without creating false certainty. The visual system should feel more like a dependable student support service than an entertainment chatbot or a conventional law-firm website.

The frontend should be developed as a responsive React and TypeScript application using a custom design system built from accessible primitives. shadcn/ui and Radix-based patterns are recommended for the foundational components because they are composable and customizable rather than a closed visual theme.1 Motion Primitives may be used selectively for polished interaction patterns, but every borrowed component must be adapted to LexAware’s design tokens, reviewed for accessibility, and recorded in the dependency and attribution register.2

1.1 Experience principles
Principle Meaning in the interface
Calm before clever Avoid visual noise, aggressive gradients, unnecessary animations, and playful copy in sensitive workflows.
Explain the next step Each major screen should answer what the user is seeing, why it matters, and what they can do next.
Show the evidence Sources, page references, review dates, confidence, and limitations should be visible at the point of use.
Never imply certainty Use “potential concern,” “needs review,” and “based on available information” instead of definitive legal verdicts.
Protect dignity Use neutral, non-judgmental language for harassment, fraud, safety, and dispute-related journeys.
Design for interruption Students may be stressed, on mobile, on slow networks, or unable to complete a workflow in one session.
Accessible by default Keyboard support, readable contrast, reduced motion, screen-reader semantics, and touch-friendly controls are mandatory.

2. Brand Identity
   2.1 Brand personality
   LexAware Student should be credible, approachable, composed, protective, and practical. It should avoid looking bureaucratic, intimidating, overly corporate, or like a generic AI tool.

The brand voice should be direct and supportive. It should not use exaggerated claims such as “guaranteed legal protection,” “instant legal solution,” or “the answer to your case.” Preferred wording includes “Understand the situation,” “Review the important parts,” “Explore your options,” and “Find appropriate help.”

2.2 Logo concept
The recommended logo combines three ideas in one simple symbol:

1 An open shield, representing safety and protection.
2 An open book or document fold, representing knowledge and document understanding.
3 A forward path or check-shaped negative space, representing the next step.

The mark should be recognizable at small sizes and should not use a literal courthouse, gavel, scales of justice, or police emblem. Those symbols can make the platform appear like an authority or legal institution.

The preferred construction is a rounded shield outline with a central open-page fold. The fold creates a subtle letter L through negative space. The logotype reads LexAware with Student as a smaller descriptor. The product name should remain “LexAware Student” in formal contexts, even if an internal short name such as “LexAware” is used in navigation.

2.3 Logo variants
Variant Use
Primary horizontal lockup Desktop header, landing page, official documents
Compact mark Mobile header, favicon, app shortcut, avatar placeholder
Monochrome dark Light backgrounds, formal reports, print
Monochrome light Dark footer, dark banner, high-contrast context
Outline mark Empty states and low-emphasis illustrations
The logo must have clear space equal to at least the width of the inner page fold. The mark should not be stretched, rotated, decorated with unapproved shadows, or placed over a busy image.

2.4 Logo design prompt for a designer or image tool
Create a minimal vector logo for “LexAware Student,” a student legal-awareness platform. Combine a rounded protective shield with an open book or document fold and a subtle forward path in negative space. Use deep navy, teal, and a small amber accent. Avoid courthouse columns, gavels, scales, police symbols, gradients, mascots, and literal legal clichés. The design must remain recognizable as a 24px favicon, work in one color, and feel calm, modern, inclusive, trustworthy, and educational.

2.5 Iconography
Use a consistent outline icon family with rounded joins and a 1.75px default stroke. Recommended icon source: Lucide React or an equivalent permissively licensed icon set. Icons must support labels rather than replace them. Safety, warning, document, search, help, and navigation icons should have stable meanings across the product.

3. Color System
   The primary palette is designed for high readability and trust. Color must never be the only way to communicate risk, status, or urgency.

3.1 Core color tokens
Token Hex Use
--ink-950 #102A43 Primary headings and high-emphasis text
--ink-800 #243B53 Body text on light surfaces
--ink-600 #486581 Secondary text and metadata
--navy-900 #0B1F33 Dark navigation, footer, and high-contrast panels
--teal-700 #0F766E Primary brand action and active states
--teal-600 #0D9488 Hover and interactive emphasis
--teal-100 #CCFBF1 Low-emphasis information surfaces
--sky-600 #0284C7 Links and informational accents
--sky-100 #E0F2FE Source and informational callouts
--amber-600 #D97706 Review-needed and attention states
--amber-100 #FEF3C7 Attention backgrounds
--rose-700 #BE123C Urgent safety and destructive action text
--rose-100 #FFE4E6 Urgent safety backgrounds
--green-700 #15803D Completed, verified, or safe-success states
--green-100 #DCFCE7 Success backgrounds
--surface-0 #FFFFFF Primary surface
--surface-50 #F8FAFC Page background
--surface-100 #F1F5F9 Cards, fields, and grouped areas
--border #D9E2EC Default border
--border-strong #9FB3C8 Focus-adjacent and high-contrast borders
3.2 Semantic status colors
Status Label Color treatment Required secondary cue
Informational Information Sky background and blue icon “Information” label or info icon
Verified Verified Green background and check icon Verification date
Attention Needs review Amber background and warning icon Text label and explanation
Urgent Get help now Rose background and alert icon Direct action and support contact
Neutral Not available Slate background Explanation of missing or unsupported data
Risk colors must not be presented as a numerical legal-risk score unless the scoring method is explicitly defined and validated. The initial product should use descriptive states rather than dramatic red/yellow/green dashboards.

3.3 Dark mode
Dark mode may be introduced after the light theme has passed accessibility and usability testing. It must use semantic tokens rather than inverted raw hex values. Dark mode must preserve source visibility, focus visibility, status distinctions, and readable document previews.

4. Typography and Content Style
   4.1 Font recommendation
   Use Inter for the interface and body text because it is highly legible across dense UI layouts and supports a broad character set. Use Manrope for large headings and selected brand moments because its shapes provide a warmer, more distinctive identity without reducing readability. If reducing dependencies is important, Inter may be used for both headings and body text.

Fonts should be self-hosted or loaded through an approved performance-conscious strategy. Use variable font files where available. Avoid more than two font families and avoid decorative typefaces in legal or safety workflows.

4.2 Type scale
Token Size Line height Weight Use
Display 48px 1.1 700 Landing-page hero only
H1 36px 1.15 700 Page title
H2 28px 1.2 700 Major section
H3 22px 1.3 650 Card or workflow section
Body large 18px 1.6 400 Explanations and lead text
Body 16px 1.55 400 Default content
Body small 14px 1.45 400 Metadata and supporting text
Caption 12px 1.4 500 Labels and timestamps
Code 13px 1.5 400 Technical or reference output
Text should use sentence case. Headings should describe the user task rather than the internal module name. For example, use “Understand your internship agreement” instead of “Document Analyzer Module.”

4.3 Content patterns
Every important explanation should use short paragraphs, descriptive subheadings, and progressive disclosure. Place the primary action near the explanation it affects. Avoid dense walls of text, unexplained legal abbreviations, and unsupported claims.

AI-generated content must visibly distinguish between the assistant’s explanation and the source-backed material. Source labels should use language such as “Based on reviewed sources” and “Last reviewed.”

5. Layout and Responsive System
   5.1 Layout principles
   The application should use a 12-column desktop grid, an 8-column tablet grid, and a 4-column mobile grid. The content width should generally remain between 1120px and 1280px on desktop. Reading-heavy content should be limited to approximately 680–760px per line-length region.

Use a 4px base spacing unit with a preferred scale of 4, 8, 12, 16, 24, 32, 40, 48, 64, and 80px. Cards should use moderate radius values rather than excessive pill shapes. Recommended radii are 8px for controls, 12px for cards, and 16px for feature panels.

5.2 Responsive behavior
Viewport Behavior
Mobile, below 640px Single-column layout, bottom or compact navigation, full-width primary actions, stacked analysis findings
Tablet, 640–1023px Two-column dashboard where space permits, collapsible navigation, readable document panels
Desktop, 1024px and above Persistent sidebar, two- or three-column dashboard, split document viewer and findings panel
Wide desktop, 1440px and above Preserve readable content width; do not stretch text or create excessive empty space
The mobile interface should not be a shrunken desktop interface. The most important action should appear first, filters should become drawers or sheets, and tables should become cards or horizontally scrollable regions with clear headers.

5.3 Navigation
The primary student navigation should contain Home, Know Your Rights, Ask Assistant, My Documents, Complaint Guides, Find Help, and Saved Items. The user menu should contain profile, privacy, accessibility, and sign-out actions.

The administrator navigation should contain Overview, Users, Knowledge, Complaint Guides, Help Resources, Feedback, Announcements, Audit, and Settings. Student and administrator navigation must be visually and technically separated by authorization.

6. Information Architecture and Screen Plan
   6.1 Public and onboarding screens
   Screen Purpose Primary action
   Landing page Explain the value and boundaries of the product Explore how it works
   Sign up Create a student account Create account
   Sign in Authenticate Continue securely
   Privacy and safety notice Explain document and AI handling Continue after understanding
   First-use orientation Set expectations and show the five main routes Start exploring
   The landing page should use a restrained hero section, a short trust statement, three capability cards, a safety boundary, and a clear sign-in action. It should not simulate a legal answer in a marketing animation.

6.2 Student screens
Screen Key content and interaction
Dashboard Welcome, quick actions, recent documents, saved topics, announcements, and urgent support banner when relevant
Rights Explorer Category cards, search, filters, article cards, source and review metadata
Article detail Summary, rights, next steps, evidence checklist, report options, sources, reviewed date
Assistant workspace Question composer, suggested topics, response sections, citations, escalation panel, feedback
Upload flow File drop, supported-format guidance, privacy notice, validation state, progress, completion
Document analysis Document viewer, findings list, page jump, attention labels, report export, next steps
Document Vault Searchable private files, status, analysis history, retention and deletion actions
Complaint wizard Stepper, safety check, fact collection, checklist, reporting routes, save progress
Help Directory Search, location filter, verified resources, contact actions, last verified date
Saved Items Saved articles, guides, resources, and reports
Settings Profile, notification preferences, privacy, accessibility, sessions, account deletion
6.3 Administrator screens
The administrator experience should prioritize queue management and content quality. A dashboard should show stale content, pending reviews, failed jobs, user-reported answers, unverified resources, and system health. Editors should work through a draft–review–publish lifecycle with preview, version history, required source fields, and review-date validation.

7. Core UX Flows
   7.1 Ask the Assistant
   Choose Ask Assistant
   -> See safety and privacy reminder
   -> Enter question
   -> Optional jurisdiction/location clarification
   -> Classify intent and urgency
   -> Show loading state with honest progress language
   -> Display explanation, assumptions, next steps, sources, and limits
   -> Offer save, feedback, complaint guide, or help directory route

The empty state should provide examples such as “What should I check in an internship bond?” rather than encouraging users to paste highly sensitive personal data. If the prompt appears urgent, the safety route should appear before the normal answer.

7.2 Analyze a document
Upload document
-> Confirm supported type and privacy notice
-> Validate file
-> Extract and classify
-> Show processing status
-> Display document and findings together
-> Jump from finding to page evidence
-> Explain limitation and next step
-> Save, export, or delete

The interface must show extraction uncertainty. A message such as “Some pages could not be read. Findings may be incomplete.” is preferable to silently showing a clean result.

7.3 Complaint guidance
The wizard should begin with a short “Are you in immediate danger?” safety gate where relevant. It should then ask only the facts needed to choose a route. A persistent progress indicator should show the current step, and the user should be able to save and return without losing completed answers.

7.4 Help directory
Each resource card should display the resource type, location, phone or web action, verification status, last verified date, and an option to report outdated information. Emergency resources should be visually prominent but not mixed with ordinary informational links.

8. Design System Components
   8.1 Foundation components
   The initial component library should include Button, IconButton, Link, Badge, Tag, Avatar, Input, Textarea, Select, Combobox, Checkbox, RadioGroup, Switch, Tooltip, DropdownMenu, Tabs, Accordion, Dialog, Drawer, Sheet, AlertDialog, Toast, Breadcrumbs, Pagination, Skeleton, EmptyState, ErrorState, Progress, Calendar, and DataTable.

These components should be built from accessible primitives, use design tokens, expose keyboard states, and avoid application-specific business logic.

8.2 LexAware-specific components
Component Purpose
SafetyNotice Explains emergency routing, privacy, and non-advisory boundaries
SourceCitation Displays source title, section/page, jurisdiction, and review date
ReviewStatusBadge Shows verified, needs review, pending, expired, or revoked states
RiskAttentionCard Shows a potentially important clause without claiming illegality
ClauseEvidenceViewer Connects a finding to document page and excerpt
AnalysisTimeline Shows asynchronous document-processing states
NextStepCard Converts explanation into one practical action
EscalationPanel Routes users to a professional, institutional, emergency, or specialist resource
ComplaintStepper Manages guided complaint workflows and saved progress
HelpResourceCard Shows verified contact information and location scope
PrivacyFileDropzone Uploads documents with type, size, privacy, and deletion guidance
ConfidenceDisclosure Explains uncertainty in classification, extraction, or retrieval
FeedbackPrompt Collects helpful/not helpful feedback and optional comments
8.3 Component API standards
Components should use controlled state where state affects business logic, support loading and error states, accept accessible labels, and expose test identifiers only when necessary. Component names should describe function rather than appearance. For example, use SourceCitation instead of BlueInfoBox.

Every component should have a Storybook story or equivalent isolated example for default, loading, empty, error, mobile, keyboard-focus, long-text, and reduced-motion states.

9. Interaction and Motion System
   Motion should clarify hierarchy, state change, and continuity. It should not distract users from legal content or delay access to an urgent action.

9.1 Motion principles
Pattern Recommended behavior
Page transition Short opacity and small vertical shift; avoid dramatic slides
Card entrance Stagger only a small group of cards; keep delay below the point where it feels slow
Assistant response Reveal sections progressively only if content is already available; do not simulate typing to create false intelligence
Upload processing Use a determinate progress indicator when possible; otherwise use a labeled indeterminate state
Drawer or dialog Use a short scale/opacity or slide transition with focus management
Finding-to-page navigation Use a subtle highlight pulse on the selected evidence, with a non-motion focus fallback
Success state Use color, icon, and text; do not rely on confetti or celebratory effects
Error state Use a calm transition and preserve the user’s input
9.2 Recommended motion libraries
Use Motion for React for application-level transitions and gestures. Use Motion Primitives for selected patterns such as animated tabs, disclosure panels, spotlight effects, text transitions, or progressive blur only when the interaction improves comprehension.2 The project should not import a large collection of animated components simply because they are available.

The Motion configuration must respect the user’s operating-system reduced-motion preference. Motion’s accessibility guidance recommends disabling transform and layout motion while preserving appropriate opacity or color transitions when reduced motion is enabled.3 LexAware should also disable parallax, autoplaying decorative media, and large-scale continuous movement for reduced-motion users.

9.3 Motion limits
Avoid infinite loops, bouncing error messages, animated legal-risk meters, auto-advancing carousels, cursor-following effects in core workflows, and large background parallax. No animation should conceal a status change, remove user input, or prevent keyboard access.

9.4 Borrowed snippets and component governance
The team may use code or component patterns from Motion Primitives, shadcn/ui, Radix UI, Lucide, and other approved sources. Borrowed code must follow this process:

4 Confirm the repository license and any attribution requirement.
5 Record the source URL, component name, version or commit, license, and modifications in docs/frontend/third-party-components.md.
6 Copy the smallest useful unit rather than importing unrelated styles or dependencies.
7 Replace colors, spacing, typography, radii, and motion values with LexAware tokens.
8 Test keyboard behavior, focus management, screen-reader behavior, mobile layout, long text, reduced motion, and loading/error states.
9 Review the code for analytics, external requests, unsafe DOM manipulation, and unnecessary bundle weight.
10 Treat copied snippets as maintained project code. Do not assume upstream updates are automatically applied.

A visually impressive component should be rejected if it harms readability, accessibility, performance, legal clarity, or maintainability.

10. Accessibility and Inclusive Design
    The frontend should target WCAG 2.2 AA practices for keyboard access, focus visibility, contrast, semantics, form errors, status announcements, and responsive reflow.4 Accessibility is especially important because users may be stressed, have disabilities, or use assistive technology to read long documents.

Required behaviors include:

• Every interactive control must be keyboard accessible.
• Focus must be visible and must move predictably into and out of dialogs and drawers.
• Form errors must identify the field, explain the problem, and preserve entered values.
• Async processing states must be announced through an appropriate live region without flooding the screen reader.
• Status must not rely on color alone.
• Touch targets should be approximately 44px or larger where practical.
• Text should remain readable at increased browser zoom and reflow without loss of functionality.
• Tables and document evidence must have meaningful headings and labels.
• Reduced-motion preferences must be honored globally and locally.
• Users must be able to stop, skip, or bypass nonessential motion and repeated navigation.

Accessibility testing should include keyboard-only navigation, screen-reader spot checks, high-contrast or forced-colors behavior, zoom testing, mobile touch testing, and automated checks using tools such as axe-core. Automated tools do not replace human review.

11. Frontend Technical Architecture
    11.1 Recommended frontend stack
    Area Recommendation
    Framework React with TypeScript and Vite
    Routing React Router with protected route boundaries
    Styling Tailwind CSS using CSS variables for design tokens
    Components shadcn/ui patterns with Radix primitives where appropriate
    Icons Lucide React or another approved consistent icon set
    Motion Motion for React; selected Motion Primitives components
    Server state TanStack Query for API caching, retries, invalidation, and loading states
    Forms React Hook Form with Zod schemas
    Charts A restrained accessible chart library only for administrator analytics
    Testing Vitest, React Testing Library, Playwright, axe-core
    Documentation Storybook or an equivalent component catalog
    Build and quality ESLint, Prettier, TypeScript strict mode, lint-staged, CI checks
    11.2 Suggested frontend structure
    apps/web/src/
    ├── app/
    │ ├── router/
    │ ├── providers/
    │ ├── layouts/
    │ └── error-boundaries/
    ├── components/
    │ ├── ui/ # Base accessible primitives
    │ ├── lexaware/ # Product-specific components
    │ └── motion/ # Approved motion wrappers and patterns
    ├── features/
    │ ├── auth/
    │ ├── dashboard/
    │ ├── rights-explorer/
    │ ├── assistant/
    │ ├── documents/
    │ ├── complaint-guides/
    │ ├── help-directory/
    │ └── admin/
    ├── hooks/
    ├── lib/
    │ ├── api-client/
    │ ├── analytics/
    │ ├── accessibility/
    │ └── validation/
    ├── styles/
    │ ├── tokens.css
    │ ├── globals.css
    │ └── themes.css
    ├── types/
    └── test/

Business rules should remain in feature modules or shared domain utilities rather than in generic UI components. API response types should be generated or kept synchronized with the FastAPI OpenAPI contract. The frontend must treat all user-controlled and AI-generated text as untrusted content and render it safely.

11.3 State and loading strategy
Use explicit states for idle, loading, success, empty, partial, error, unauthorized, and unavailable-provider conditions. Skeletons should preserve the eventual layout. Loading indicators should not imply that an AI response is being “thought about” if the system is waiting for a network request.

For document analysis, the UI should poll or subscribe to a job status endpoint and display the current processing stage. The user should be able to navigate away and return without losing the job or creating a duplicate upload.

11.4 Performance targets
The frontend should minimize JavaScript on public pages, lazy-load administrator and document-analysis routes, compress images, avoid unnecessary animation work, and keep the initial dashboard responsive on mid-range mobile devices. Large document previews and analysis findings should be virtualized or paginated where needed.

Measure Core Web Vitals, route transitions, upload progress, analysis completion time, API failure rate, and bundle size in staging and production. Do not add a visual library without measuring its bundle and runtime cost.

12. Trust, Privacy, and Safety in the Interface
    The UI should repeat important safety information at the moment it becomes relevant, not hide it in a general legal notice. Upload screens should state that documents are private by default, explain supported formats, discourage unnecessary personal information, and provide deletion guidance.

AI responses should display their source basis, review date, limitations, and escalation route. Document findings should display the page or section evidence. The interface must never present a generated answer in the same visual style as a verified source without labeling the distinction.

Error messages should be specific but not reveal internal details. For example, “We could not read this PDF. Try a text-based PDF or contact support.” is appropriate; a stack trace or provider name is not.

13. Frontend Quality Gates
    A frontend feature is complete only when it has a defined user outcome, responsive layout, empty/loading/error states, keyboard behavior, focus behavior, screen-reader labels, reduced-motion behavior, analytics or audit decisions, unit tests, an end-to-end path where appropriate, and a Storybook or equivalent component example.

The release should be blocked when a core workflow has inaccessible controls, unreadable contrast, missing error recovery, misleading status language, unsafe source presentation, broken mobile behavior, or animation that ignores reduced-motion preferences.

13.1 UX acceptance checklist
Area Acceptance question
Clarity Can a first-time student explain what the screen does?
Trust Can the user see what is sourced, generated, uncertain, or reviewed?
Actionability Is the next appropriate action visible without searching?
Safety Are urgent routes and limitations shown at the right time?
Accessibility Can the workflow be completed with keyboard and assistive technology?
Resilience Does the interface preserve input and recover from network or provider failure?
Responsiveness Does the workflow remain usable on a narrow mobile viewport?
Performance Does motion and visual polish avoid delaying the task?
Consistency Do components use the shared tokens and interaction rules?

14. Implementation Roadmap for the Frontend
    Phase Frontend deliverables Exit criteria
1. Visual foundation Logo, tokens, typography, global styles, navigation shell, accessibility baseline Token usage is centralized; keyboard focus and responsive shell pass review
1. Core component system Base controls, cards, dialogs, forms, alerts, empty/error states, Storybook catalog Components support loading, error, mobile, keyboard, and reduced-motion states
1. Student journeys Authentication, dashboard, Rights Explorer, article detail, Help Directory Main browsing and help journeys work on mobile and desktop
1. Guided workflows Assistant workspace, complaint wizard, file upload, job progress, document findings Users can complete, pause, resume, and recover from errors
1. Trust and governance UI Citations, review badges, escalation panels, feedback, privacy settings, deletion flows Source and safety states are visible and understandable
1. Interaction polish Selected Motion Primitives, micro-interactions, transitions, admin analytics Motion improves comprehension, reduced-motion behavior passes, bundle impact is accepted
1. Hardening Accessibility audit, visual regression, performance profiling, browser matrix, final UX testing Release checklist passes with no critical UX or accessibility defects

1. Recommended Initial Visual Composition
   The landing page should use a light surface-50 background, a compact navy navigation bar or white header, a restrained teal primary action, and a hero section with the shield-book logo. The first fold should communicate three facts: LexAware is for students, it helps users understand documents and situations, and it does not replace professional legal assistance.

The authenticated dashboard should use a calm two-column layout. The main column should contain the welcome message, four quick-action cards, and recent activity. The secondary column should contain announcements, saved items, and a compact “Need urgent help?” route where relevant. The quick-action cards should use simple line illustrations or icons rather than heavy decorative images.

The document-analysis screen should use a split layout on desktop: the document or extracted text on the left and findings on the right. On mobile, findings should appear first, followed by a page-linked document view. Each finding should use a descriptive label, a short explanation, evidence location, and one next action.

The assistant should look like a structured workspace rather than a consumer chat clone. Responses should be divided into labeled sections, with citations and an escalation card. The message composer should include a privacy hint and avoid suggesting that users paste passwords, identity numbers, or unnecessary personal information.

16. Final Frontend Definition
    The LexAware Student frontend should be a responsive, accessible, source-aware interface that makes complex legal-awareness journeys understandable to students. Its design system should combine a calm navy and teal identity, readable typography, evidence-oriented cards, descriptive status labels, and restrained motion.

The project may use open-source components and snippets from Motion Primitives, shadcn/ui, Radix UI, Lucide, and similar libraries. However, borrowed code must be adapted, tested, attributed, and governed as part of the project’s own frontend system. The goal is not to collect impressive effects. The goal is to help students understand the situation, recognize uncertainty, and take an appropriate next step with confidence that is properly calibrated.

References
Implementation note: Before using any third-party component or snippet in production, confirm the exact repository license, attribution requirements, dependency security, maintenance status, and compatibility with LexAware’s accessibility and privacy requirements.
