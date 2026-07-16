# Provider security boundary

Remote providers, tools, external fetch, shell/code execution and secret values are forbidden. A future integration may reference an uppercase environment-variable name only; values never enter persistence, audit, logs, API responses or browser code.
