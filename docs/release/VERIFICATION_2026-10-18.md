# Idea-first release verification · 2026-10-18

Base reviewed: PR #15 head 53bd4b146abc2ea8f9e859f1ccba4a6154089cc5. This revision adds shared stage numbering, correct configured-provider wording, and an accurate post-export next step. The public README from main is preserved and updated.

## Automated checks

- Locked dependencies; local isolated PostgreSQL 17 container, synthetic data and deterministic offline provider.
- Migration upgrade and Alembic drift checks passed.
- Complete base quality gate passed: 461 Python tests, 42 Web tests, 13 JavaScript contract checks, formatting, lint, strict types and production build.
- Frontend fixes: 44 Web tests, lint, strict types and production build passed. Two regression tests cover 8-stage versus 9-stage numbering and exported ZIP guidance. Backend source is unchanged from the reviewed base.

## Actual desktop browser journey

Created a synthetic coffee-shop project; structured the demo idea; entered audience and CTA; saved and reloaded the draft; confirmed Brief; generated three concepts and explicitly selected the second; generated Script, Storyboard and Shot Plan; checked the chosen concept, 30-second duration and CTA; approved the synthetic bundle; created and exported the delivery package. Refresh recovered the seven artifacts and export record. A downloaded ZIP matched the displayed SHA-256 and passed archive CRC validation.

ZIP: 3,618 bytes; SHA-256 863e926ca836a1fcc476e89b7f88dddb45d70b1259c155d197c4768cbc2fa783. Files: README.txt, manifest.json, script.json, shot-plan.csv, shot-plan.json, storyboard.json.

## Scope and limits

This is a locally usable release of the preproduction workflow, not a hosted production service or generated video. No paid/real provider call, cross-device discovery, full mobile testing, multitab stress test or production load test was performed. The browser's automatic download event was not exposed by the test harness; the page's explicit fallback download link was used and the downloaded bytes were verified. Earlier case-study screenshots/video remain historical demonstrations.
