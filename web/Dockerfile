# Build context is the repo root (see docker-compose.yml).
FROM node:22-alpine AS build
WORKDIR /app

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ .

# Vite bakes VITE_* vars into the built JS at build time, not at container
# start — so this has to be a build arg, not a runtime environment variable.
ARG VITE_API_BASE_URL=http://127.0.0.1:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /usr/share/caddy
COPY web/Caddyfile /etc/caddy/Caddyfile
EXPOSE 80 443
