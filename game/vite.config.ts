import { resolve } from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  base: './', // 相対パスで出力し、どのサーバー/サブディレクトリでも動くようにする
  server: { port: 5173 },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 2000, // Phaser 本体が大きいため
    // ページを増やしたらここに追加する
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        three: resolve(import.meta.dirname, '3d.html'),
      },
    },
  },
});
