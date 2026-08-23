FROM node:22-alpine AS dependencies
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY web/package.json ./web/package.json
COPY admin/package.json ./admin/package.json
COPY mobile/package.json ./mobile/package.json
RUN npm install --workspace @drovixa/web --include-workspace-root --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /workspace
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencies /workspace/node_modules ./node_modules
COPY --from=dependencies /workspace/web/node_modules ./web/node_modules
COPY package.json package-lock.json ./
COPY web ./web
ARG NEXT_PUBLIC_API_URL=/api/drovixa
ARG NEXT_PUBLIC_SENTRY_DSN
ARG NEXT_PUBLIC_APP_ENV=production
ARG RELEASE=drovixa@0.9.0
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN \
    NEXT_PUBLIC_APP_ENV=$NEXT_PUBLIC_APP_ENV \
    NEXT_PUBLIC_RELEASE=$RELEASE \
    RELEASE=$RELEASE
RUN npm run build --workspace @drovixa/web

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /workspace/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /workspace/web/.next/static ./web/.next/static
COPY --from=builder --chown=nextjs:nodejs /workspace/web/public ./web/public
USER nextjs
EXPOSE 3000
CMD ["node", "web/server.js"]
