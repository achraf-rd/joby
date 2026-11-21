// Writes the API's OpenAPI spec to packages/contracts/openapi/api.json without
// starting the HTTP server or connecting to the database.
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module.js';
import { buildOpenApiDocument } from './openapi.js';

const out = resolve(
  import.meta.dirname,
  '../../../packages/contracts/openapi/api.json',
);

const app = await NestFactory.create(AppModule, { logger: false });
writeFileSync(out, JSON.stringify(buildOpenApiDocument(app), null, 2) + '\n');
await app.close();
