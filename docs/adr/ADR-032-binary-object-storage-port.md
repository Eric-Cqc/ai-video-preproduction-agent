# ADR-032: Binary object storage port

Status: Accepted for Stage 7

## Decision

Introduce a server-side `StoragePort` and immutable `SourceObject` attached one-to-one to a `SourceAssetVersion`. Storage keys are opaque, random, and server-generated. Local/test/ci use `LocalFilesystemStorageAdapter`; non-local environments fail closed until a reviewed adapter is configured. Filename and tenant identifiers never form storage paths.

The port exposes only bounded stage, immutable finalize, read, and delete capabilities. Provider-specific details do not enter domain or presentation code.

## Consequences

The local adapter proves the boundary without selecting a production provider. The local filesystem is a replaceable assumption, not a deployment recommendation.

## Re-evaluation triggers

Select or revise the adapter when production storage, retention, encryption/KMS, malware scanning, regional residency, or direct upload requirements are approved.
