import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// A interface conversa com a API pelos mesmos endpoints que um supervisório usaria. Em
// desenvolvimento o proxy mantém tudo na mesma origem — o que dispensa CORS e reproduz o
// arranjo de produção, onde o nginx serve o estático e encaminha /api ao serviço Python.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/api/, ""),
      },
    },
  },
});
