FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=/api/v1
ARG NEXT_PUBLIC_CSRF_COOKIE_NAME=seller_wb_csrf
ARG NEXT_PUBLIC_ENABLE_FINANCE=false
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_CSRF_COOKIE_NAME=$NEXT_PUBLIC_CSRF_COOKIE_NAME
ENV NEXT_PUBLIC_ENABLE_FINANCE=$NEXT_PUBLIC_ENABLE_FINANCE
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ARG NEXT_PUBLIC_API_URL=/api/v1
ARG NEXT_PUBLIC_CSRF_COOKIE_NAME=seller_wb_csrf
ARG NEXT_PUBLIC_ENABLE_FINANCE=false
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_CSRF_COOKIE_NAME=$NEXT_PUBLIC_CSRF_COOKIE_NAME
ENV NEXT_PUBLIC_ENABLE_FINANCE=$NEXT_PUBLIC_ENABLE_FINANCE
COPY package.json package-lock.json ./
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./next.config.ts

EXPOSE 3000

CMD ["npm", "run", "start"]
