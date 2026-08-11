FROM node:22.18.0-alpine3.22 AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_ENABLE_DEMO=false
ENV VITE_ENABLE_DEMO=${VITE_ENABLE_DEMO}
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27.5-alpine3.21
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
