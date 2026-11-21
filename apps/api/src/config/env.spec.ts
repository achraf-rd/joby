import { validateEnv } from './env.js';

const base = {
  DATABASE_URL: 'postgresql://joby:joby@localhost:5432/joby',
  INTERNAL_HMAC_SECRET: 'x',
  JWT_ACCESS_SECRET: 'y',
};

describe('validateEnv', () => {
  it('applies defaults', () => {
    const env = validateEnv(base);
    expect(env.PORT).toBe(3000);
    expect(env.NODE_ENV).toBe('development');
  });

  it('coerces PORT from string', () => {
    expect(validateEnv({ ...base, PORT: '4000' }).PORT).toBe(4000);
  });

  it('rejects a missing secret', () => {
    const { JWT_ACCESS_SECRET: _omit, ...rest } = base;
    expect(() => validateEnv(rest)).toThrow(/JWT_ACCESS_SECRET/);
  });
});
