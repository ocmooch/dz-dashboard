import createClient from "openapi-fetch";

import type { paths } from "./schema";

// The one and only way the SPA reaches data: a typed client generated from the
// BFF's OpenAPI schema. baseUrl "/" hits the same origin (Vite proxies to the
// BFF in dev; a reverse proxy or same host serves both in production).
export const api = createClient<paths>({ baseUrl: "/" });
