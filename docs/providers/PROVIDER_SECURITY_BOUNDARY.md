# Provider security boundary

ADR-064 permits only the server-side DeepSeek `deepseek-v4-flash` Adapter at the exact approved
HTTPS endpoint. It uses no SDK, tools, external fetch, redirects, inherited proxies or client
configuration. All other remote providers, shell/code execution and secret values remain forbidden.
The key never enters persistence, audit, logs, API responses or browser code.
