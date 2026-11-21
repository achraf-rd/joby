# Build context: repository root.
FROM node:22-slim AS base
RUN corepack enable
WORKDIR /repo

FROM base AS build
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @joby/api build
RUN pnpm --filter @joby/api deploy --prod /out

FROM node:22-slim
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /out .
EXPOSE 3000
# Apply pending Prisma migrations, then start.
CMD ["sh", "-c", "node_modules/.bin/prisma migrate deploy && node dist/main.js"]
