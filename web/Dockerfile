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

# This is the only container facing the internet directly, so it's the one
# that least deserves to run as root.
#
# Two things are needed. Ports below 1024 are normally root-only, so grant
# just the bind capability instead of the whole account. And Caddy writes
# issued certificates under /data (XDG_DATA_HOME in the base image), so that
# has to be writable by the new user or renewal fails.
#
# NOTE for an existing deployment: the chown below only affects the empty
# directories inside the image, which Docker copies into a *newly created*
# volume. A caddy_data volume that already holds certificates keeps its
# root ownership, and renewal would start failing silently until the current
# certificate expires. Run this once on the server after pulling:
#
#   docker compose run --rm --user root web chown -R 10001:10001 /data /config
RUN apk add --no-cache --virtual .setcap libcap \
    && setcap cap_net_bind_service=+ep /usr/bin/caddy \
    && apk del .setcap \
    && adduser -D -H -u 10001 caddyapp \
    && mkdir -p /data /config \
    && chown -R 10001:10001 /data /config
USER caddyapp

EXPOSE 80 443
