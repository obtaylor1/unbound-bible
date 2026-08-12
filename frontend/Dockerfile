FROM node:22.18.0-alpine3.22@sha256:1b2479dd35a99687d6638f5976fd235e26c5b37e8122f786fcd5fe231d63de5b AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_ENABLE_DEMO=false
ENV VITE_ENABLE_DEMO=${VITE_ENABLE_DEMO}
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine@sha256:65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0
ENV API_UPSTREAM=api:8000
COPY frontend/nginx.conf /etc/nginx/templates/default.conf.template
COPY --chmod=0755 frontend/15-dynamic-resolver.envsh /docker-entrypoint.d/15-dynamic-resolver.envsh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
