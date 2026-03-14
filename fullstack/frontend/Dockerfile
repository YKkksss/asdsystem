FROM node:20-alpine AS build

WORKDIR /app

COPY . .

RUN if [ -f package.json ]; then \
      if [ -f package-lock.json ]; then npm ci; else npm install; fi && npm run build; \
    else \
      mkdir -p dist && cp placeholder/index.html dist/index.html; \
    fi

FROM nginx:1.27-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
