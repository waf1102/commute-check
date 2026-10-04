# Commute Check frontend

Svelte 5 / SvelteKit with the Node adapter. See the [root README](../README.md) for the full setup.

```sh
npm ci
npm run dev
```

The Python backend should be running on port 8000. The SvelteKit `/api/*` gateway uses `BACKEND_URL` (default `http://127.0.0.1:8000`) in both development and production. This variable is server-side; do not use a `VITE_` browser URL.

```sh
npm run check
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests require the Python dependencies from `../requirements.txt`. They launch their own backend and frontend on ports 8001 and 4173, use an isolated database, and replace external providers. Traces and screenshots appear in `test-results` on failure; inspect with `npx playwright show-trace <trace.zip>`.

For a production Node process:

```sh
BACKEND_URL=http://127.0.0.1:8000 ORIGIN=http://localhost:3000 node build
```

Use the actual public HTTPS origin when deployed. `npm run format` formats source with Prettier; `npm run format:check` checks formatting. `npm run test:watch` watches unit tests.

The `cookie` override in `package.json` keeps SvelteKit's transitive cookie parser on the patched 0.7 line while retaining the existing SvelteKit major version. Revisit the override when upgrading SvelteKit.
