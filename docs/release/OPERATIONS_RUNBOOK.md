# Local operations runbook

`make rc-up` starts PostgreSQL, migrates to head, builds Web/contracts, starts API and Web, and
waits up to 30 seconds for bounded health checks. `make rc-check` verifies database head, both
HTTP surfaces, writable local storage and the full smoke. `make rc-down` stops the two processes
and Compose without deleting volumes. Logs and PID files are ignored under `.local/rc`.
