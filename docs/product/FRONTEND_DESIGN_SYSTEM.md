# Production Desk design system

## Foundations

- **Typography:** Songti-family headings for artifact titles; system Chinese sans-serif for
  operational controls. The product does not request remote fonts.
- **Color:** paper `#f7f2e8`, ink `#18231d`, operational green `#29462e`, and review amber
  `#b56d2a`. Color never supplies status without adjacent text.
- **Layout:** a 14rem process rail, flexible task area, and 20rem context panel on desktop.

## Interaction and accessibility

Controls retain visible keyboard focus, semantic headings, a skip link, labelled forms and
`aria-live` operation feedback. Desktop, tablet and narrow-phone breakpoints are 1024px and
640px. Details disclosure keeps project records inspectable without making raw values the
primary artifact view.

## Local API boundary

The browser client only sends the temporary local tenant context entered in Settings and an
idempotency key for mutations. It uses an eight-second abort boundary, retries only safe reads
after transient gateway failures, and maps authorization, conflict and validation responses to
plain language. It intentionally never renders internal digests, provider data, SQL errors or
constraint names.
