# ==============================================================================
# CyberShield AI — Hyperledger Fabric Gateway Production Container
# ==============================================================================

FROM node:18-bullseye-slim AS builder

WORKDIR /app

# Install build dependencies for grpc native modules if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci --only=production

# Final runtime stage
FROM node:18-bullseye-slim

WORKDIR /app

# Copy production dependencies
COPY --from=builder /app/node_modules ./node_modules
COPY package*.json ./
COPY src/ ./src/

ENV NODE_ENV=production
ENV GATEWAY_PORT=4000
ENV GATEWAY_HOST=0.0.0.0

EXPOSE 4000

USER node

CMD ["node", "src/api/server.js"]
