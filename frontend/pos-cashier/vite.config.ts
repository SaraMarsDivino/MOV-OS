import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const isProd = mode === 'production';

  return {
    plugins: [react()],
    // In production, assets are served by Django at /static/pos-cashier/...
    base: isProd ? '/static/pos-cashier/' : '/',
    build: {
      // Write build output into Django's static directory so collectstatic/WhiteNoise can serve it.
      outDir: path.resolve(__dirname, '../../static/pos-cashier'),
      emptyOutDir: true,
      manifest: true,
      rollupOptions: {
        // Entrypoints used by Django templates.
        // - movos-pages.tsx: router for several React-admin pages (window.__MOVOS_REACT_PAGE__)
        // - main.tsx: full POS cashier app mounted at /cashier/
        input: {
          'movos-pages': path.resolve(__dirname, 'src/movos-pages.tsx'),
          'pos-cashier': path.resolve(__dirname, 'src/main.tsx'),
        },
      },
    },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
      // Backend (Django) endpoints used by the cashier UI
      '/cashier': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // Auth/login flows
      '/accounts': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // Other backend routes that might be opened from cashier actions
      '/reports': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/users': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/products': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/sucursales': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      },
    },
  };
});
