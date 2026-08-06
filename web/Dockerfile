# Interface: build em Node, entrega em nginx.
#
# A imagem final não carrega Node nem as dependências de desenvolvimento — só o estático
# resultante. O `npm run build` executa também os verificadores de tokens e de contraste
# (ADR-015), de modo que uma violação do design system reprova a construção da imagem, e
# não apenas o build local.
FROM node:22-alpine AS construcao

WORKDIR /web

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=construcao /web/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
