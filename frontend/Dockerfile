# ASZDA Studio web app image.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/next.config.ts ./next.config.ts
# ASZDA_API_URL is read when the server starts (set it in docker-compose or your platform).
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
