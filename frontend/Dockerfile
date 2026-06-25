FROM node:22-alpine AS build

WORKDIR /frontend

ARG VITE_API_BASE_URL=
ARG VITE_ENABLE_DEV_LOGIN=false
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_ENABLE_DEV_LOGIN=$VITE_ENABLE_DEV_LOGIN

COPY package.json .
RUN npm install

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist /usr/share/nginx/html

EXPOSE 80
