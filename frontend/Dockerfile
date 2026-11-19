# FinTrack web image: build the static app, then serve it with nginx.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# "/api" = same origin; nginx below forwards it to the backend.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# The unprivileged variant runs nginx as a normal user (not root) and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine
# The image renders /etc/nginx/templates/*.template with env vars at startup.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# Optional TRUSTED_PROXIES support (see the script).
COPY --chmod=755 docker/40-fintrack-real-ip.sh /docker-entrypoint.d/40-fintrack-real-ip.sh
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_URL=http://backend:8000 \
    CSP_CONNECT_SRC="'self'" \
    TRUSTED_PROXIES=""
EXPOSE 8080
