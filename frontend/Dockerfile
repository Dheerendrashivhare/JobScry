# Angular build -> static files served by Nginx, which also reverse-proxies /api.
# Build context is the REPO ROOT (see docker-compose.yml) because the Nginx config
# lives in infra/, outside the frontend directory.
FROM node:20-alpine AS build

WORKDIR /app

# Node 20 is deliberate: Angular is pinned to 19 because the owner's machine runs
# Node 20.11.1 (see PROGRESS.md, Phase 9 deviation). Keep this in step with that pin.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf

# Angular's application builder emits the browser bundle under dist/<project>/browser.
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 80
