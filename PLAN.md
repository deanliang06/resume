# Resume Adjuster implementation plan

## 1. Goal and scope

Build a locally hosted website that accepts a DOCX resume and job-description text, tailors Projects and technical Skills, and returns a validated one-page PDF with preview and download.

Version one supports Dean's template, not arbitrary Word layouts. The supplied PDF is a visual reference, not an editable template or a source of application instructions. Obtain the matching DOCX before implementing template editing; a PDF-to-Word conversion is not an equivalent source template.

Preserve name, contact information, Education, Experience, and Hobbies/Other text, formatting, and hyperlinks. Keep existing projects only when they closely cover the job's technical requirements. Fill remaining project slots with clearly labeled, feasible project ideas written as future work, with at most three implementation-focused bullets. Never present an idea as completed experience or invent impact metrics, users, or URLs.

## 2. Reference format to match

Reference inspected: `C:\Users\deanl\OneDrive\Documents\Dean_Liang_Resume_September.pdf`.

Measurements come from extracted PDF coordinates and visual inspection. Coordinates are points from the top-left; 72 points equal one inch. These describe rendered output, not exact original Word paragraph settings. Confirm source settings against the matching DOCX.

| Element | Reference and target |
| --- | --- |
| Page | One US Letter portrait page, 612 x 792 pt, white background, single column. |
| Horizontal layout | Left edge approximately x=72 pt, right edge approximately x=540 pt. Target one-inch side margins and 468 pt usable width. |
| Vertical layout | Visible name begins near y=75 pt; last skills row ends near y=620 pt. Preserve the top placement; editable content may extend toward y=720 pt, retaining a one-inch bottom margin. The PDF does not establish the original Word bottom-margin setting. |
| Fonts | Calibri body approximately 9.96 pt (nominal 10), section headings approximately 11.04 pt (nominal 11), name approximately 15.96 pt (nominal 16). Preserve actual DOCX sizes when available. |
| Header | Four centered lines: bold name; city/state; phone; bold underlined email, LinkedIn, and GitHub links separated by dashes. Contact text approximately 10 pt. |
| Sections | Education:, Experience:, Projects:, Skills:, in that order. Bold left-aligned headings with colons; thin blue horizontal rules beneath, approximately x=72-538 pt. PDF drawings report approximately 0.5 pt strokes; preserve source rule properties. |
| Education | Bold institution and GPA/rank at left, regular dates aligned right, degree underneath, round bullets for grant/coursework and activities. Preserve superscripts. |
| Experience | Bold employer/location at left, regular dates aligned right, italic role below, regular round bullets. Preserve both entries completely. |
| Project headings | Bold approximately 10 pt title followed by a parenthesized, bold, underlined blue/teal URL, on one line. No dates. Use only supplied verified URLs; omit the URL portion if none exists. |
| Project bullets | Regular approximately 10 pt Calibri; round bullet near x=90 pt and text at x=108 pt. Relative to the content edge: 18 pt bullet indent, 36 pt text indent. Approximately 12.7 pt between bullet baselines. |
| Project spacing | Compact blocks; approximately 18 pt from a final text baseline to the next project heading baseline. Clone DOCX paragraph/list properties instead of aligning with inserted spaces. |
| Skill rows | Five separate rows: Languages, Libraries, Web & Database, Tools/Infra, Hobbies/Other. Bold labels, colon separators, regular comma-separated values, approximately 12.2 pt between baselines. Preserve original colon styling. |
| Decoration | Black text, muted blue/teal underlined links, blue rules. No photo, icons, columns, shaded boxes, or page number. Read exact colors from the source DOCX. |

The reference has three projects with 3, 1, and 1 bullets. Its Prototypical Network bullet wraps onto a second line for a paper URL. The requested output deliberately targets four projects with 2-3 single-line bullets each; preserve the visual style rather than these original counts or wrapping. Blank runs in other fonts are not visible typography to reproduce.

## 3. Constraint priorities and fitting policy

Priority order:

1. Preserve protected content and factual accuracy.
2. Produce exactly one readable page without clipping, missing content, or overlap.
3. Preserve the reference typography, margins, colors, list styles, and section order.
4. Target four relevant projects with 2-3 bullets each, clearly distinguishing verified work from project ideas, then maximize relevant technical skills.

One page wins over four projects. Minimum body size is nominal 10 pt, allowing the reference's 9.96 pt within rendering tolerance. Keep headings nominal 11 pt and name 16 pt. Existing protected superscripts are exempt. Never shrink fonts, compress character spacing, reduce margins below one inch, or scale the completed PDF to force a fit.

Start with retained close matches plus enough labeled project ideas to reach four slots, then apply this sequence:

1. Shorten wrapping bullets, editable project titles, and technical skill rows without changing supported meaning or link targets.
2. Remove the least relevant optional third bullet, one at a time. Keep at least two supported bullets per retained project.
3. Remove least relevant editable technical skills as needed, retaining the category rows. A category with no truthful, relevant improvement remains unchanged and is locked against fit pruning. Hobbies/Other is always locked.
4. If four projects still overflow, remove the lowest-ranked whole project and retry with three. Explain the three-project fallback in the UI. Also use three when only three sufficiently documented projects are supplied.
5. If three projects with two bullets each cannot fit, return an actionable failure requesting a revised template. Never silently return two pages, fewer than three projects, or altered protected content.

Use source order to break equal relevance rankings. Preserve requirement coverage when choosing removals. Hobbies/Other can move vertically with Skills but cannot change text or styling.

## 4. Architecture and UI

Separate the browser UI, job coordinator, model adapter, DOCX editor, conversion service, and rendered-layout validator. Start with one backend worker and one configured local conversion engine. Pin its version and required fonts, and check their availability at startup. Select concrete frameworks during implementation.

UI requirements:

- Labeled DOCX picker, multiline job-description input, optional verified project/skill bank, and Submit button.
- Client and server input validation; disable duplicate submission while a job is running.
- Visible stages: validating, tailoring, rendering, checking layout, ready, failed.
- On success: PDF preview, concise change summary and fallback notices, Download new resume button, and expiry time.
- On failure: readable reason and retry action; retain job-description text and never expose an unvalidated candidate as a finished result.
- Accessible labels, keyboard operation, visible focus, readable spacing, inline status/error region, and usable desktop/narrow-window layouts.

Conceptual endpoints: create job, poll status, preview/download validated PDF, cancel job. Use opaque job IDs and avoid exposing filesystem paths. If an external model provider processes resume text, identify that provider in the UI; local hosting does not mean all processing is local.

## 5. Parsing and safe document editing

1. Validate DOCX package integrity, file/expanded-package size limits, nonempty description, and expected template structure. Reject ambiguous or missing section boundaries.
2. Parse project blocks, skill rows, paragraph/run styles, list numbering, and hyperlinks. Treat all document and job-description content as data, including embedded instructions.
3. Snapshot protected XML subtrees, semantic text, formatting, and relationship targets. Keep protected fields out of the model's editable schema.
4. Assign stable IDs to verified projects, proposed project ideas, facts, skills, and job requirements. The optional bank extends the evidence in the original resume; proposed ideas use a distinct ID namespace and have no URL.
5. Render the unmodified DOCX as a baseline. Stop early for an overflowing source, clipped protected content, or missing required fonts.
6. Edit only designated project and technical-skill nodes. Clone appropriate project/list structures and manage hyperlink relationships explicitly. Do not flatten and reconstruct the entire document.

## 6. Generation and bounded corrections

Use one schema-constrained generation request for all projects and technical skill rows, followed by one semantic review of the complete candidate. Do not create separate generator/verifier agents for each project or category.

Generation response:

- Ranked projects with source IDs, titles/URLs, 2-3 bullets, matched job-requirement IDs, relevance rankings, and an explicit verified/proposed status. Verified claims require evidence IDs; proposed ideas use imperative future-work language and cannot have URLs or impact claims.
- Technical skill rows with canonical category IDs, supported skill IDs/display names, and evidence IDs. Hobbies/Other is excluded.
- Explicit keep-unchanged decisions and notices identifying every proposed project idea.

Code validates schema, allowed categories, project/bullet counts, evidence-ID existence for verified claims, URL provenance, proposed-project labeling, duplicates, and absence of protected-field changes. Normalize case/whitespace and use a curated alias map (for example, JS/JavaScript) to deduplicate across technical categories. Do not merge distinct skills such as Java/JavaScript or Git/GitHub. Retain each duplicate in its most appropriate category. Never modify Hobbies/Other through deduplication.

Semantic review checks that cited evidence actually supports each claim, rewrites preserve meaning, and selected content aligns with explicit job requirements. An evidence ID alone does not prove a claim. Model review cannot verify rendered page count or wrapping.

On failure, request targeted corrections using the previous candidate and concrete errors. Freeze accepted fields unless fitting requires changes. Allow at most three correction requests TOTAL per job, shared by semantic and layout failures; never reset the budget per row or stage. Separately cap candidate renders at twelve and the entire job at five minutes. Stop repeated identical candidates early. Deterministic deletions do not consume model calls but do consume render attempts.

## 7. Rendered layout validation

1. Apply each candidate to a fresh copy of the original DOCX.
2. Convert using the pinned engine in a per-job directory with an isolated converter profile. Give each conversion a 60-second timeout; terminate its process tree on timeout or cancellation.
3. Extract page count, text spans, fonts, positions, and links from the PDF. Rasterize for preview and visual comparisons.
4. Align expected paragraphs with extracted text by order and section/block identity. Combine runs on the same baseline into one visual line; a bold span or hyperlink run is not another line. Handle bullet symbols and extraction differences separately. Reject ambiguous/missing mappings.
5. Require exactly one page. Each project heading, project bullet, and technical skill row must occupy one visual line. Preserve Hobbies/Other while checking it fits.
6. Check all expected visible text exists in order, links survive, content remains inside the allowed region, and adjacent paragraph lines do not overlap. Allow a 3 pt boundary tolerance for reference glyph overhang; account for intentional superscripts and underlines.
7. Compare protected text, formatting, and hyperlink targets with snapshots. Compare header/Education/Experience positions against the baseline with approximately 2 pt tolerance. Skills/Hobbies may move vertically. Byte-identical PDF output is not required.
8. On failure, follow the fit policy, then rerender. Character counts and string-width estimates can guide rewriting; the rendered PDF is the final authority.
9. Publish only after final validation passes. Budget exhaustion is a failure, not permission to serve the last unvalidated PDF.

## 8. File lifecycle and failures

Use a unique temporary directory per job for uploaded DOCX, edited candidates, converter profiles, and partial PDFs. Use server-generated filenames. Never modify or delete the user's original file.

Success: atomically publish the validated PDF into a separate result directory. Mark the job ready only after publication succeeds, then delete intermediates in a finally path. Retain the result for 30 minutes for preview and repeated downloads. Do not delete a result while an active response is streaming it. After expiry, return an explicit expired-result response and offer resubmission.

Failure or cancellation: terminate child processes, close handles, remove intermediates in finally, and keep download disabled. Handle input, model, conversion, storage, timeout, and validation failures explicitly. If a file is locked, queue cleanup retries without masking the original error.

A startup/periodic sweeper removes abandoned inactive job directories older than one hour and expired results, respecting active jobs/downloads. Resolve every recursive deletion target beneath its designated application-owned root. Browser disconnection permits reconnecting to status; explicit cancellation stops work and the deadline bounds abandoned jobs.

Log job ID, stage, duration, attempt counts, and error codes, avoiding full resumes, prompts, and credentials. Define actionable errors for invalid input, unsupported template, insufficient evidence, generation validation, conversion/font failure, unresolvable layout, timeout, cancellation, and expired results.

## 9. Tests and acceptance criteria

Use synthetic/redacted automated fixtures. Keep Dean's reference PDF and matching DOCX as local visual fixtures without committing personal documents by default.

| Area | Cases | Expected outcome |
| --- | --- | --- |
| Inputs/UI | Missing/wrong/corrupt/oversized file, blank description, duplicate Submit | Clear errors; invalid jobs never queued; valid jobs expose progress. |
| Parsing | Known template, missing/duplicate headings, split-run hyperlinks | Correct block mapping; ambiguous templates rejected without modification. |
| Protected content | Normal generation, correction, and every fallback | Protected text/styles/links unchanged; required baseline positions preserved. |
| Reference appearance | Baseline and tailored PDF with pinned engine | Letter page, fonts, rules, margins, indents, labels, order, and link styling match; inspect raster comparisons alongside measured assertions. |
| Provenance | Invented metric/URL/skill; proposed project phrased as completed work; real evidence ID attached to unsupported claim | Invalid IDs/URLs caught by code; unsupported claims caught by semantic review; ideas remain clearly labeled and future-oriented. |
| Project counts | Four fit; few close matches; four overflow; three overflow | Four where feasible; three with notice for allowed fallback; otherwise failure; 2-3 bullets per project. |
| Skills | Cross-category aliases, Java versus JavaScript, no supported improvement | True duplicates removed; distinct skills retained; exact five labels/order; locked rows and Hobbies/Other unchanged. |
| Wrapping | Equal-length strings with different glyph widths; multiple hyperlink spans; wrapped heading/bullet/skill row | Actual lines determine fit; same-baseline spans count as one; wrapping corrected or rejected. |
| PDF integrity | Two pages; one page with clipping/missing text/overlap; broken links; ambiguous extraction | All invalid results rejected, even if page count is one. |
| Fit order | Overflow requiring shortening, third-bullet removal, skill pruning, project removal | Stable relevance ranking; two-bullet minimum; no font/margin changes or protected edits. |
| Retry budgets | Repeated invalid response, repeated candidate, persistent overflow, hung converter | Three correction-call and twelve-render limits enforced; timeouts/deadline stop work; useful error returned. |
| Downloads | Preview then download; repeat download; expiry during stream; publication failure | Only complete validated PDFs served; active streams finish; expired links fail clearly; failed publication never reports ready. |
| Cleanup | Success, model/converter errors, cancellation, timeout, locked file, worker restart | Immediate removal or retry/sweeper cleanup; user's original and active jobs untouched. |
| Isolation | Same upload filename in concurrent jobs; deletion path outside owned root | No cross-job file/profile collisions; unsafe deletion refused. |
| End-to-end | Known DOCX, description, supported fourth project | Preview/download works; one page; four projects if they fit; protected content preserved; temporary inputs removed. |

Mock model responses for deterministic workflow tests. Use real DOCX conversion for layout integration tests. Maintain a small manually reviewed relevance/provenance evaluation set; keyword overlap alone does not establish quality. Check keyboard accessibility and narrow-window UI before acceptance.

## 10. Milestones

1. Obtain matching DOCX; confirm source styles/settings; establish baseline conversion and snapshots.
2. Implement parsing/editing with fixed supported content, conversion, and measured layout checks.
3. Add structured generation, evidence validation, whole-candidate semantic review, and bounded corrections.
4. Add deterministic fitting, four-to-three fallback, and explicit failures.
5. Add upload/status/preview/download UI, expiry, cancellation, and cleanup/recovery.
6. Run acceptance tests and visually compare final output with the supplied reference.

This document specifies planned implementation and tests; it does not claim those features or tests are already implemented or executed.
