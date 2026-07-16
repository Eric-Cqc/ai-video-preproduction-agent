# ADR-056: Visual prompt safety boundary

Status: Accepted for Stage 12

Generation and negative prompts are bounded inert output data. They are never executed, fetched, logged in audit, or sent to an external Provider in this stage.

URL, shell, code, tool and prompt-injection-like text is treated as untrusted
content and rejected by contract/semantic validation; no automatic repair occurs.
