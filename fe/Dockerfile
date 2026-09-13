# ==============================================================================
# Stage 1: Build Frontend SPA
# ==============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests
COPY package.json package-lock.json* yarn.lock* ./

# Install dependencies with legacy-peer-deps for React 19 compatibility
RUN npm install --legacy-peer-deps || yarn install --frozen-lockfile

# Copy source code
COPY . .

# Build arguments for browser-facing API and LiveKit URLs
ARG REACT_APP_BACKEND_URL
ARG REACT_APP_LIVEKIT_URL

ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}
ENV REACT_APP_LIVEKIT_URL=${REACT_APP_LIVEKIT_URL}

# Build static production bundle
RUN npm run build || yarn build

# ==============================================================================
# Stage 2: Serve Bundle with Nginx Alpine
# ==============================================================================
FROM nginx:1.25-alpine

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
