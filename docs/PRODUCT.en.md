# Exam Radar — MVP v1

[繁體中文](PRODUCT.md) | **English**

Exam Radar is a search engine for school exam information across Taiwan. Its architecture takes inspiration from STA's frontend/backend split, with an independent implementation that does not copy STA's code or data.

## Phase one

Audience: high school students. Planned pilot: 20 Taipei high schools, their first periodic exam, with HTML and PDF sources prioritized.

Users can search schools and exams, filter by grade and subject, view exam scopes and sources, compare exams with the same academic year, semester, and exam number, and check announcement versions. Administrators can initiate crawls and review uncertain extraction results.

## Required data quality

- Use official websites and public attachments as sources. Do not bypass logins, CAPTCHAs, or access controls.
- Determine the source school from registered records and allowed domains; do not trust a document's self-declared school identity alone.
- Preserve source references, fetch timestamps, content hashes, and available page numbers for every published scope.
- Group revisions for the same school, academic year, semester, exam number, and grade under the same exam.
- Confidence scores alone cannot replace validation. Uncertain extractions require review.
- Clearly separate demo data from real crawled data. Demo records must not trigger school crawls.

## Targets and measurement

Discovery recall >90%, extraction accuracy >95%, duplicate rate <2%, wrong-school rate <0.5%, crawler success >95%, and source traceability 100%.

These are acceptance targets, not achieved results. Build a manually labeled pilot announcement dataset and evaluate at the source-announcement level. The number of fetched pages is not a success metric.

## Future work

Supplemental search-engine discovery, Playwright for JavaScript pages, human-calibrated structured LLM extraction, OCR, legacy DOC/XLS conversion, a complete official school list, textbook chapter mapping across publishers, public past exam papers, and notifications.

Similar exam scopes do not imply the same curriculum or textbooks. Establish textbook mappings before claiming chapter coverage.
