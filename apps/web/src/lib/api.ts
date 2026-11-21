import type { Api } from '@joby/contracts';
import createClient from 'openapi-fetch';

/** Typed client for the Nest API, generated from its OpenAPI spec. */
export const api = createClient<Api.paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? '/api',
  credentials: 'include',
});
