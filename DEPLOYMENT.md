# 42Voice Deployment Guide

This document is the canonical reference for deploying the 42Voice stack.
It complements `deploy.sh` and the environment templates (`.env.docker.example`,
`.env.local.example`).

## Canonical deployment stack

The **canonical production stack is the root `docker-compose.yml`**.
`scripts/deploy.sh`, `voice-agent/entrypoint.sh`, and this repo's CI assume it.

| Concern | Canonical configuration |
| --- | --- |
| Compose file | `docker-compose.yml` (repo root) |
| Backend/worker | `voice-agent` image + `./entrypoint.sh backend` / `./entrypoint.sh worker` |
| Frontend | `fe` service; build args `REACT_APP_BACKEND_URL`, `REACT_APP_LIVEKIT_URL` |
| Postgres | External (Supabase); never containerized |
| Redis | `redis:7-alpine` with `REDIS_PASSWORD` |
| LiveKit SFU | `livekit/livekit-server` via `LIVEKIT_CONFIG` |
| LiveKit SIP | `livekit/sip` via `SIP_CONFIG_BODY` |
| LiveKit Egress | `livekit/egress` via `EGRESS_CONFIG_BODY` |

The alternative files are **not** used in production:

- `docker-compose.local.yml` - local development stack.
- `voice-agent/livekit/docker-compose.yml` - low-level LiveKit dev services.
- `livekit.yaml`, `livekit.local.yaml`, `voice-agent/livekit/*.yaml` - reference
  templates only; they are **not** mounted by any compose file and must never
  be committed with real values.

## Credentials are injected from the environment only

No credential values are committed or defaulted anywhere in the compose files.
Verified with `docker compose config`:

```
$ docker compose -f docker-compose.yml config
error ... REDIS_PASSWORD is required
error ... LIVEKIT_API_KEY is required
error ... LIVEKIT_API_SECRET is required
```

The stack refuses to start unless these variables are provided.

### Required environment variables

| Variable | Purpose |
| --- | --- |
| `REDIS_PASSWORD` | Redis `requirepass`; used by livekit, sip, egress, backend, worker |
| `LIVEKIT_API_KEY` | LiveKit API key (`keys:` section) |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `DATABASE_URL` / `PGHOST`+`PGPORT`+`PGUSER`+`PGPASSWORD`+`PGDATABASE` | Supabase Postgres |
| `DB_SSL_MODE` | `auto` (default) / `disable` / `require` / `verify-full` |
| `SEED_SUPER_ADMIN_PASSWORD` + `SEED_FINANCE_ADMIN_PASSWORD` + `SEED_RESELLER_PASSWORD` + `SEED_CLIENT_PASSWORD` | Initial user passwords, used once (idempotent) |
| `JWT_ACCESS_SECRET`, `JWT_REFRESH_SECRET` | Auth token signing |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SIP_DOMAIN` | Outbound/inbound PSTN |
| `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, `CARTESIA_API_KEY`, `OPENAI_API_KEY` | STT/TTS/LLM providers |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME` | Recordings/transcripts |
| `FRONTEND_URL`, `BACKEND_URL` | CORS allow-list (scheme + host only) and links |

## Networking model

- `redis`, `livekit`, `egress` run on the bridge network `app-network` and
  address each other by **service name** (`redis:6379`, `ws://livekit:7880`).
- The `sip` service uses `network_mode: host` because SIP/RTP media needs the
  wide UDP port range. **In host mode Docker service names do not resolve**, so
  the SIP config (`SIP_CONFIG_BODY`) must use the host loopback ports:
  `ws://127.0.0.1:7880` and `redis: 127.0.0.1:6379`.
- Do not "fix" the SIP `ws_url` back to `ws://livekit:7880` while `sip` uses
  host networking - that breaks SIP registration.
- The SIP service additionally requires `LIVEKIT_SIP_PUBLIC_URI`
  (e.g. `sip:voice@your-ip-or-host:<5060>`) to be advertised correctly.

## Egress configuration

Egress reads its config from `EGRESS_CONFIG_BODY`, where the `${...}` variables
are expanded by the compose engine **before** reaching egress.
Do NOT switch egress back to `EGRESS_CONFIG_FILE` + a template file containing
literal `${LIVEKIT_API_KEY}` - egress does not interpolate those placeholders.

## Startup order

Compose `depends_on` handles ordering (`redis` first, then `livekit`,
`sip`, `egress`, then `backend`/`voice-agent`). The backend entrypoint runs
`init_db.py`, which applies schema and seeds initial users idempotently
(`ON CONFLICT ... DO NOTHING`) - existing passwords are never overwritten.

## Deploying

```bash
cp .env.docker.example .env      # fill in all values
./scripts/deploy.sh              # builds and starts the canonical stack
```

`scripts/deploy.sh` loads `.env` (`export $(grep -v '^#' .env | xargs)`) and
runs `docker compose build` and `docker compose up -d`.