# RC visual acceptance

Existing DOM and responsive checks cover the Production Desk at desktop, tablet (1024px) and
phone (390px) breakpoints. The rail reflows to four columns, forms become single-column, focus is
visible, long project data wraps, progress uses live text, and downloads remain explicit. This
environment has no repository-pinned screenshot runner; no dependency was installed and no
screenshots are committed. Manual RC review should cover long filenames, UUIDs, loading/error
states, keyboard order, touch targets and horizontal overflow before external release.
