import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    catalog_smoke: {
      executor: 'ramping-vus',
      stages: [
        { duration: '30s', target: 10 },
        { duration: '60s', target: 25 },
        { duration: '15s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<750'],
  },
};

const baseUrl = (__ENV.API_ORIGIN || 'http://localhost:8000').replace(/\/$/, '');

export default function () {
  const health = http.get(`${baseUrl}/api/v1/health/ready`);
  check(health, { 'ready is 200': (response) => response.status === 200 });

  const catalog = http.get(`${baseUrl}/api/v1/content?page=1&limit=20`);
  check(catalog, { 'catalog is successful': (response) => response.status === 200 });
  sleep(1);
}
