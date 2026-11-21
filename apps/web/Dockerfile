# Build context: repository root.
FROM node:22-slim AS build
RUN corepack enable
WORKDIR /repo
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @joby/web build

FROM caddy:2-alpine
COPY apps/web/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /repo/apps/web/dist /srv
EXPOSE 80
