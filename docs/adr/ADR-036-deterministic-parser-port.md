# ADR-036: Deterministic parser port

Status: Accepted for Stage 8

## Decision

Add a server-selected ParserPort producing canonical ExtractedDocument schema v1. Implement only standard-library plain text, CSV and JSON adapters. PDF, DOCX and XLSX are explicit unsupported-media outcomes until separately approved parser dependencies exist. Parsers do not fetch URLs, execute code/macros, load dynamic plugins or perform OCR.

## Re-evaluation triggers

Review for approved richer formats, OCR, parser sandboxing or independently deployable parsing evidence.
