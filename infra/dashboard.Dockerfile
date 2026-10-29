FROM node:24-alpine AS build
WORKDIR /app
RUN npm install -g pnpm@11.25.0
COPY apps/dashboard/package.json apps/dashboard/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/dashboard ./
RUN pnpm build
FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=8031 API_INTERNAL_URL=http://api:8030
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 8031
CMD ["node","server.js"]
