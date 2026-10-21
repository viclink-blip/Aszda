# ASZDA Studio web app image.
FROM node:22-slim
WORKDIR /app

# Next.js fixes the /api forwarding address when the app is BUILT, not when it
# starts, so the API address must be known here. docker-compose passes
# http://api:5000 (the API container); change it for other setups.
ARG ASZDA_API_URL=http://api:5000
ENV ASZDA_API_URL=$ASZDA_API_URL

COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

ENV NODE_ENV=production
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
