import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// A interface conversa com a API pelos mesmos endpoints que um supervisório usaria. Em
// desenvolvimento o proxy mantém tudo na mesma origem — o que dispensa CORS e reproduz o
// arranjo de produção, onde o nginx serve o estático e encaminha /api ao serviço Python.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // `localhost` resolve para ::1 antes de 127.0.0.1 no Windows, e o padrão do Vite
    // escuta só em um dos dois — o endereço que não coube passava a recusar conexão.
    // `true` faz escutar em todas as interfaces, e os dois nomes respondem.
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/api/, ""),
      },
    },
  },
});
