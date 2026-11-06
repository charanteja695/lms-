# The web app: built once with Node, served by nginx, which also forwards /api to the API gateway (same origin, so the
# refresh cookie stays first-party and no CORS is needed). VITE_* values are baked into the bundle at build time.

FROM node:22.12-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_APP_NAME=LMS
ARG VITE_ORGANIZATION_NAME=
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_NOTIFICATION_POLL_SECONDS=60
ARG VITE_LIVE_REFRESH_SECONDS=30
ENV VITE_APP_NAME=$VITE_APP_NAME \
    VITE_ORGANIZATION_NAME=$VITE_ORGANIZATION_NAME \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_NOTIFICATION_POLL_SECONDS=$VITE_NOTIFICATION_POLL_SECONDS \
    VITE_LIVE_REFRESH_SECONDS=$VITE_LIVE_REFRESH_SECONDS
RUN npm run build

FROM nginx:1.27-alpine
# Rendered into conf.d at start by the image's envsubst step: API_UPSTREAM (where the gateway is), API_MAX_BODY (match the
# gateway's MAX_BODY_BYTES) and STORAGE_ORIGIN (object storage the browser uploads to and reads from, for the CSP).
COPY nginx/*.template /etc/nginx/templates/
COPY --from=build /app/dist /usr/share/nginx/html
ENV API_UPSTREAM=http://api-gateway:8000 \
    API_MAX_BODY=32m \
    STORAGE_ORIGIN=http://minio:9000
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz || exit 1
