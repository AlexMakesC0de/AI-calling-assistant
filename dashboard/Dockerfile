# syntax=docker/dockerfile:1.7
#
# Production image for the Twilio dashboard.
# Multi-stage: deps → builder → runner, using Next.js standalone output.
# Runtime image ships only what the server actually needs.
#
# Alpine is chosen for image size. Prisma's engine is dynamically linked
# against libssl, so `openssl` is apk-installed in every stage and the
# schema pins `linux-musl-openssl-3.0.x` as a binary target.

# ─────────────────────────────────────────────────────────────────────────
# 1. deps — install node_modules with cached layer
# ─────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS deps
WORKDIR /app

# libc6-compat: some npm packages rely on glibc-ish behaviour on Alpine.
# openssl:      Prisma engine links against libssl at install + runtime.
RUN apk add --no-cache libc6-compat openssl

# Copy only dependency manifests first so this layer is cached unless the
# lockfile changes.
COPY package.json package-lock.json ./
# Prisma's `postinstall` script runs `prisma generate`, which needs the
# schema to be present at install time.
COPY prisma ./prisma
RUN npm ci

# ─────────────────────────────────────────────────────────────────────────
# 2. builder — compile the Next.js app
# ─────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app
RUN apk add --no-cache libc6-compat openssl

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Re-run in case the schema changed after `npm ci`'s postinstall snapshot.
RUN npx prisma generate
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────
# 3. runner — minimal runtime image
# ─────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS runner
WORKDIR /app

# openssl is required for the Prisma query engine at runtime.
RUN apk add --no-cache openssl

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Drop to an unprivileged user.
RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 --ingroup nodejs nextjs

# Next's standalone output contains a tiny server.js plus exactly the
# node_modules it traced as reachable (including Prisma engines, thanks
# to `serverExternalPackages` in next.config.ts).
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Pre-create the recordings dir owned by `nextjs`. When a named volume is
# mounted here under docker-compose, Docker initialises the empty volume
# from this path, inheriting its uid/gid — without this the volume mount
# point is root-owned and the unprivileged process can't write.
RUN mkdir -p /recordings && chown nextjs:nodejs /recordings
RUN mkdir -p /data/shared && chown nextjs:nodejs /data/shared

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
