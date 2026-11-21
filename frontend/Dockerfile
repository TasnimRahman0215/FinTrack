# FinTrack web image: build the static app, then serve it with nginx.
# Base images are pinned by digest (tag kept for readability); Dependabot proposes updates.
FROM node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# "/api" = same origin; nginx below forwards it to the backend.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# The unprivileged variant runs nginx as a normal user (not root) and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e
# The image renders /etc/nginx/templates/*.template with env vars at startup.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# Optional TRUSTED_PROXIES support (see the script).
COPY --chmod=755 docker/40-fintrack-real-ip.sh /docker-entrypoint.d/40-fintrack-real-ip.sh
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_URL=http://backend:8000 \
    CSP_CONNECT_SRC="'self'" \
    TRUSTED_PROXIES=""
EXPOSE 8080
