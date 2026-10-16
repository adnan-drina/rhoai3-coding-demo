# Persona sessions

The demo signs in as two personas, an administrator and a developer, each with its own kubeconfig named in `.env`
(`RHOAI_ADMIN_KUBECONFIG`/`RHOAI_ADMIN_USER`, `RHOAI_DEVELOPER_KUBECONFIG`/`RHOAI_DEVELOPER_USER`). Their OAuth tokens
expire; `validate.sh` then warns that a persona session has expired.

| Script | When to run |
|---|---|
| `login.sh [admin\|developer] [--private-window]` | Before a demo, or when `validate.sh` warns that a persona session expired. Opens a browser login per persona and saves the session to that persona's kubeconfig only. Use `--private-window` when the browser already holds another persona's session. |
