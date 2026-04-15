FROM node:20-alpine AS base
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app

# ── Dependencies ───────────────────────────────────────────────────────────────
FROM base AS deps
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/pwa/package.json apps/pwa/package.json
COPY backend/packages/logger/package.json backend/packages/logger/package.json
COPY backend/packages/types/package.json backend/packages/types/package.json
RUN pnpm install --frozen-lockfile

# ── Build ──────────────────────────────────────────────────────────────────────
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/pwa/node_modules ./apps/pwa/node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter @anjal/pwa build

# ── Production ─────────────────────────────────────────────────────────────────
FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/apps/pwa/public ./apps/pwa/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/pwa/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/pwa/.next/static ./apps/pwa/.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "apps/pwa/server.js"]
