# Local backup and recovery

Back up only in a stopped local RC. Use PostgreSQL's installed `pg_dump` to a new, explicitly
named file and copy `.local/source-objects` to a new destination; refuse an existing destination.
Never run this procedure against a production-like environment. Before restore, verify the target
database and storage destination, stop services, retain a second backup, and never overwrite
automatically. After restore run `make db-current`, `make db-check`, then `make rc-check`; download
the existing ZIP again and compare its recorded SHA-256 checksum. Cloud backup is unsupported.
