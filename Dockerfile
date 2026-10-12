FROM nginx:stable-alpine

COPY nginx.conf /etc/bailian/nginx.conf.template
COPY docker/render-nginx-config.sh /docker-entrypoint.d/40-render-nginx-config.sh
RUN chmod 755 /docker-entrypoint.d/40-render-nginx-config.sh
COPY web/index.html /usr/share/nginx/html/index.html

EXPOSE 80
