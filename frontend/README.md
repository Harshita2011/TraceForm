# TraceForm frontend

Next.js 16 / React 19 interface for the TraceForm API. See the [project README](../README.md) for installation and the complete three-process startup.

From this directory:

```text
npm ci
npm run dev
```

Copy `.env.example` to `.env.local`. Use `NEXT_PUBLIC_API_URL=/api/backend`, server-only `TRACEFORM_API_URL=http://127.0.0.1:8000`, and `NEXT_PUBLIC_USE_MOCK=false` for the connected workspace. Provider keys and installation credentials must never go in public environment variables.

`npm test`, `npm run lint`, `npx tsc --noEmit` and `npm run build` are the frontend checks. The UI needs both the API and independent worker for generation and benchmark scoring.

Hosted setup is documented in [Vercel deployment](../VERCEL_DEPLOYMENT.md); live deployment is deferred. Local operation, first-owner setup, limits and recovery are documented in [local development](../LOCAL_DEVELOPMENT.md).
