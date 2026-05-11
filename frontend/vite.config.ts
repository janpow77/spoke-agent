import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  base: '/admin/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5182,
    proxy: {
      '/api': {
        target: 'http://localhost:7844',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:7844',
        changeOrigin: true,
      },
    },
  },
})
