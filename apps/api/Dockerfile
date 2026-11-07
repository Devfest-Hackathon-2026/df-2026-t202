# Build from the repo root:
#   docker build -f apps/api/Dockerfile -t rtt-api .
FROM node:22-slim AS build
WORKDIR /repo
RUN corepack enable
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml* tsconfig.base.json ./
COPY packages/shared/package.json packages/shared/
COPY apps/api/package.json apps/api/
RUN pnpm install --frozen-lockfile --filter @rtt/api...
COPY packages/shared packages/shared
COPY apps/api apps/api
RUN pnpm --filter @rtt/api build \
 && pnpm --filter @rtt/api deploy --prod --legacy /out \
 && cp -r apps/api/dist /out/dist

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /out /app
USER node
EXPOSE 8080
CMD ["node", "dist/index.js"]
