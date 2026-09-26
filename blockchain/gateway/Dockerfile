FROM node:22-alpine
WORKDIR /srv/gateway
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force
COPY server.js ./
USER node
EXPOSE 8080
CMD ["node", "server.js"]
