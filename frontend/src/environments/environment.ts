export const environment = {
  production: false,
  // Relative on purpose: `ng serve` proxies /api to the backend (proxy.conf.json) and
  // Nginx does the same in production. No CORS layer needed on the backend either way.
  apiUrl: '/api/v1',
};
