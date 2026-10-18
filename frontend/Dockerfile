# Frontend image, built in two stages.

# Stage 1: build the React app with Node.
FROM node:24-alpine AS build
WORKDIR /app

# Install dependencies first, so this layer is cached between code changes.
COPY package.json package-lock.json ./
RUN npm ci

# Then copy the source code and build the static files into /app/dist.
COPY . .
RUN npm run build

# Stage 2: serve the static files with Nginx.
FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80