import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: "dist",
  },
  server: {
    // Только для `npm run dev` вне Docker — в проде реверс-прокси (Caddy/аналог, ещё не
    // заведён, см. CLAUDE.md "Открытый вопрос") будет проксировать /api сам. Порт 8000 —
    // тот же, на котором `uvicorn api.main:app` слушает внутри контейнера `api`
    // (см. docker-compose.yml, сервис api).
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
