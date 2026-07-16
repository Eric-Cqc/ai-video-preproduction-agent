# ADR-033: Streaming upload verification

Status: Accepted for Stage 7

## Decision

Accept a bounded `application/octet-stream` body for an existing `SourceAssetVersion`. Compute observed SHA-256 and byte size incrementally while writing a staging object. Empty, oversized, media-type-invalid, checksum-mismatched, and size-mismatched requests fail before an available object is recorded.

Declared metadata remains immutable on `SourceAssetVersion`; observed verified metadata belongs to `SourceObject`. The entire body must never be held in memory. Multipart is not implemented because it would require an unapproved dependency.

## Re-evaluation triggers

Review transport when multipart metadata, resumable uploads, browser direct uploads, or limits above 100 MiB are required.
