FROM node:20-alpine AS base
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app

# ── Dependencies ───────────────────────────────────────────────────────────────
FROM base AS deps
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY backend/services/identity/package.json backend/services/identity/package.json
COPY backend/packages/logger/package.json backend/packages/logger/package.json
COPY backend/packages/types/package.json backend/packages/types/package.json
COPY backend/packages/db/package.json backend/packages/db/package.json
RUN pnpm install --frozen-lockfile

# ── Build ──────────────────────────────────────────────────────────────────────
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/backend/services/identity/node_modules ./backend/services/identity/node_modules
COPY --from=deps /app/backend/packages ./backend/packages
COPY backend/services/identity ./backend/services/identity
COPY tsconfig.base.json ./
RUN pnpm --filter @anjal/identity build

# ── Production ─────────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 appgroup && adduser --system --uid 1001 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appgroup /app/backend/services/identity/dist ./dist
COPY --from=builder --chown=appuser:appgroup /app/node_modules ./node_modules
USER appuser
EXPOSE 4001
CMD ["node", "dist/index.js"]
