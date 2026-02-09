FROM node:20-alpine AS builder
WORKDIR /app

# Build arguments with default values
ARG VITE_BACKEND_URL=/api
ARG VITE_KEYCLOAK_URL=http://127.0.0.1:8081

# Set environment variables for Vite
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
ENV VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL}

# Install dependencies and build
COPY package.json package-lock.json ./
RUN npm ci

# Build the frontend
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
