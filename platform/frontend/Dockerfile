FROM node:20-slim AS base
WORKDIR /app
ARG BACKEND_URL=http://backend:8001
ENV BACKEND_URL=${BACKEND_URL}
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3002
CMD ["npm", "start"]
