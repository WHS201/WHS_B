# syntax=docker/dockerfile:1

# --- build stage: Vite 정적 빌드 ---
FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# OAuth 클라이언트 ID 등은 빌드타임에 주입된다 (vite: import.meta.env.VITE_*)
ARG VITE_GOOGLE_CLIENT_ID
ARG VITE_KAKAO_REST_API_KEY
ARG VITE_TURNSTILE_SITE_KEY
RUN npm run build

# --- runtime stage: nginx 로 정적 파일 서빙 + /api 프록시 ---
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
