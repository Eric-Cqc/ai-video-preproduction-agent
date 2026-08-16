# Production Desk design system

## Foundations

- **Typography:** Songti-family headings for artifact titles; system Chinese sans-serif for
  operational controls. The product does not request remote fonts.
- **Color:** the current CSS token layer uses paper `#f6f1e6`, paper-deep `#ebe3d2`, card
  `#fffdf7`, ink `#17231d`, muted `#667169`, faint `#98a095`, line `#d4d8ca`, strong line
  `#bdc7b6`, moss `#29462e`, moss-soft `#e6eee3`, moss-pale `#f1f5ed`, rust `#a44f2c`,
  rust-soft `#f5e3d7`, gold `#c88838`, gold-soft `#f5e9d4`, blue `#3d6170`, blue-soft
  `#e7eff0`, danger `#a8483b`, and danger-soft `#fae4df`. Color never supplies status
  without adjacent text.
- **Layout:** a 14rem process rail, flexible task area, and 20rem context panel on desktop.

## Interaction and accessibility

Controls retain visible keyboard focus, semantic headings, a skip link, labelled forms and
`aria-live` operation feedback. The current responsive thresholds are 1180px, 850px and
640px. Details disclosure keeps project records inspectable without making raw values the
primary artifact view.

## Local API boundary

The browser client only sends the temporary local tenant context entered in Settings and an
idempotency key for mutations. It uses an eight-second abort boundary, retries only safe reads
after transient gateway failures, and maps authorization, conflict and validation responses to
plain language. It intentionally never renders internal digests, provider data, SQL errors or
constraint names.
