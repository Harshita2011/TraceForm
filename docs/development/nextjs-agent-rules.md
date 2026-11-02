# Working on the Next.js frontend

Read the installed version's relevant guides under `frontend/node_modules/next/dist/docs/` before changing frontend framework code. This application uses Next.js 16, whose APIs and conventions may differ from older versions.

The repository intentionally keeps all tracked Markdown under `docs/`. `agentRules: false` in `frontend/next.config.ts` disables generated `AGENTS.md` and `CLAUDE.md` files in the frontend root. Their generated names are also ignored in Git so opting in locally does not clutter the repository.

Follow the frontend's existing patterns and run `npm test`, `npm run lint`, `npx tsc --noEmit` and a production build for relevant changes. See [frontend setup](frontend.md) and [contribution guidance](../CONTRIBUTING.md).
