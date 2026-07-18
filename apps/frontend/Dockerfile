FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
# Prefer npm ci; fall back to npm install if npm's exit handler flakes under Docker.
RUN npm ci || npm install --no-audit --no-fund
COPY . .
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM alpine:3.21 AS export
COPY --from=build /app/dist /dist
CMD ["sh", "-c", "rm -rf /output/* && cp -a /dist/. /output/"]
