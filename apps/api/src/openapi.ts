import type { INestApplication } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';

export function buildOpenApiDocument(app: INestApplication) {
  const config = new DocumentBuilder()
    .setTitle('Joby API')
    .setVersion('0.0.0')
    .addBearerAuth()
    .build();
  return SwaggerModule.createDocument(app, config);
}
