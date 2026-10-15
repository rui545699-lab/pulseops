# PulseOps Frontend

Next.js, TypeScript, and Tailwind CSS product experience for the PulseOps
FastAPI Product API.

## Local development

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

`NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000`. The backend
allows `http://localhost:3000` by default; additional origins can be configured
through backend `CORS_ORIGINS`.

## Verification

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

The frontend tests use injected API responses and never contact DeepSeek or
BigQuery.
