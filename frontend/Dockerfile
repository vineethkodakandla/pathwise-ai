# PathWise AI — Frontend Dashboard (React 18 + Vite)
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Build for production (Vite outputs to dist/)
COPY . .
RUN npm run build

# --- Production stage: serve with nginx ---
FROM nginx:alpine

# Copy Vite build output (outDir configured as "build" in vite.config.ts)
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx config that proxies /api and /ws to api-gateway
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
