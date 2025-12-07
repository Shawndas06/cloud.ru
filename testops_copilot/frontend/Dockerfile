# Multi-stage build для оптимизации
FROM node:20-alpine AS builder

WORKDIR /app

# Копируем package files
COPY package.json vite.config.js ./
COPY index.html ./

# Устанавливаем зависимости
RUN npm install

# Копируем исходники
COPY src ./src

# Собираем приложение
RUN npm run build

# Production stage
FROM nginx:alpine

# Копируем собранное приложение
COPY --from=builder /app/dist /usr/share/nginx/html

# Копируем конфигурацию nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открываем порт
EXPOSE 80

# Запускаем nginx
CMD ["nginx", "-g", "daemon off;"]

