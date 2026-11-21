-- pgvector for opportunity embeddings (D5). Requires a role allowed to create extensions on first run.
CREATE EXTENSION IF NOT EXISTS vector;

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "app";

-- CreateEnum
CREATE TYPE "app"."UserRole" AS ENUM ('owner', 'admin', 'member');

-- CreateEnum
CREATE TYPE "app"."RemotePreference" AS ENUM ('any', 'remote', 'hybrid', 'onsite');

-- CreateEnum
CREATE TYPE "app"."MatchStatus" AS ENUM ('new', 'saved', 'dismissed');

-- CreateEnum
CREATE TYPE "app"."RunStatus" AS ENUM ('queued', 'running', 'awaiting_approval', 'completed', 'failed', 'cancelled');

-- CreateEnum
CREATE TYPE "app"."ApplicationStatus" AS ENUM ('draft', 'awaiting_approval', 'approved', 'submitted', 'failed', 'rejected');

-- CreateEnum
CREATE TYPE "app"."ApplicationChannel" AS ENUM ('email', 'ats_form', 'manual');

-- CreateEnum
CREATE TYPE "app"."FileKind" AS ENUM ('cv_upload', 'cv_render', 'cover_letter', 'other');

-- CreateTable
CREATE TABLE "app"."tenants" (
    "id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "plan" TEXT NOT NULL DEFAULT 'free',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "tenants_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."users" (
    "id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "email" TEXT NOT NULL,
    "password_hash" TEXT NOT NULL,
    "role" "app"."UserRole" NOT NULL DEFAULT 'owner',
    "email_verified_at" TIMESTAMPTZ,
    "token_version" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."refresh_tokens" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "family_id" UUID NOT NULL,
    "token_hash" TEXT NOT NULL,
    "expires_at" TIMESTAMPTZ NOT NULL,
    "revoked_at" TIMESTAMPTZ,
    "replaced_by" UUID,
    "user_agent" TEXT,
    "ip" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "refresh_tokens_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."profiles" (
    "id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "version" INTEGER NOT NULL,
    "facts" JSONB NOT NULL,
    "raw_cv_file_id" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "profiles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."preferences" (
    "user_id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "roles" TEXT[],
    "locations" TEXT[],
    "remote" "app"."RemotePreference" NOT NULL DEFAULT 'any',
    "salary_min" INTEGER,
    "languages" TEXT[],
    "sources" TEXT[],
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "preferences_pkey" PRIMARY KEY ("user_id")
);

-- CreateTable
CREATE TABLE "app"."opportunities" (
    "id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "source" TEXT NOT NULL,
    "external_id" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "company" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "location" TEXT,
    "description" TEXT NOT NULL,
    "posted_at" TIMESTAMPTZ,
    "embedding" vector(1536),
    "dedupe_hash" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "opportunities_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."matches" (
    "tenant_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "opportunity_id" UUID NOT NULL,
    "score" DOUBLE PRECISION NOT NULL,
    "rationale" TEXT,
    "status" "app"."MatchStatus" NOT NULL DEFAULT 'new',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "matches_pkey" PRIMARY KEY ("user_id","opportunity_id")
);

-- CreateTable
CREATE TABLE "app"."runs" (
    "id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "type" TEXT NOT NULL,
    "status" "app"."RunStatus" NOT NULL DEFAULT 'queued',
    "last_seq" INTEGER NOT NULL DEFAULT 0,
    "started_at" TIMESTAMPTZ,
    "finished_at" TIMESTAMPTZ,
    "error" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."run_events" (
    "run_id" UUID NOT NULL,
    "seq" INTEGER NOT NULL,
    "type" TEXT NOT NULL,
    "step" TEXT,
    "data" JSONB NOT NULL,
    "ts" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "run_events_pkey" PRIMARY KEY ("run_id","seq")
);

-- CreateTable
CREATE TABLE "app"."applications" (
    "id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "opportunity_id" UUID NOT NULL,
    "run_id" UUID,
    "cv_file_id" UUID,
    "letter" TEXT,
    "validation" JSONB,
    "status" "app"."ApplicationStatus" NOT NULL DEFAULT 'draft',
    "channel" "app"."ApplicationChannel",
    "submitted_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "applications_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."files" (
    "id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "key" TEXT NOT NULL,
    "mime" TEXT NOT NULL,
    "size" BIGINT NOT NULL,
    "kind" "app"."FileKind" NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "files_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."usage" (
    "id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "run_id" UUID,
    "model" TEXT NOT NULL,
    "input_tokens" INTEGER NOT NULL,
    "output_tokens" INTEGER NOT NULL,
    "cost_usd" DECIMAL(12,6) NOT NULL,
    "ts" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "usage_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "app"."users"("email");

-- CreateIndex
CREATE INDEX "users_tenant_id_idx" ON "app"."users"("tenant_id");

-- CreateIndex
CREATE UNIQUE INDEX "refresh_tokens_token_hash_key" ON "app"."refresh_tokens"("token_hash");

-- CreateIndex
CREATE INDEX "refresh_tokens_user_id_idx" ON "app"."refresh_tokens"("user_id");

-- CreateIndex
CREATE INDEX "refresh_tokens_family_id_idx" ON "app"."refresh_tokens"("family_id");

-- CreateIndex
CREATE INDEX "profiles_tenant_id_idx" ON "app"."profiles"("tenant_id");

-- CreateIndex
CREATE UNIQUE INDEX "profiles_user_id_version_key" ON "app"."profiles"("user_id", "version");

-- CreateIndex
CREATE INDEX "preferences_tenant_id_idx" ON "app"."preferences"("tenant_id");

-- CreateIndex
CREATE INDEX "opportunities_tenant_id_dedupe_hash_idx" ON "app"."opportunities"("tenant_id", "dedupe_hash");

-- CreateIndex
CREATE UNIQUE INDEX "opportunities_tenant_id_source_external_id_key" ON "app"."opportunities"("tenant_id", "source", "external_id");

-- CreateIndex
CREATE INDEX "matches_tenant_id_idx" ON "app"."matches"("tenant_id");

-- CreateIndex
CREATE INDEX "runs_tenant_id_status_idx" ON "app"."runs"("tenant_id", "status");

-- CreateIndex
CREATE INDEX "applications_tenant_id_status_idx" ON "app"."applications"("tenant_id", "status");

-- CreateIndex
CREATE UNIQUE INDEX "files_key_key" ON "app"."files"("key");

-- CreateIndex
CREATE INDEX "files_tenant_id_idx" ON "app"."files"("tenant_id");

-- CreateIndex
CREATE INDEX "usage_tenant_id_ts_idx" ON "app"."usage"("tenant_id", "ts");

-- AddForeignKey
ALTER TABLE "app"."users" ADD CONSTRAINT "users_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."refresh_tokens" ADD CONSTRAINT "refresh_tokens_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."profiles" ADD CONSTRAINT "profiles_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."profiles" ADD CONSTRAINT "profiles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."profiles" ADD CONSTRAINT "profiles_raw_cv_file_id_fkey" FOREIGN KEY ("raw_cv_file_id") REFERENCES "app"."files"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."preferences" ADD CONSTRAINT "preferences_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."preferences" ADD CONSTRAINT "preferences_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."opportunities" ADD CONSTRAINT "opportunities_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."matches" ADD CONSTRAINT "matches_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."matches" ADD CONSTRAINT "matches_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."matches" ADD CONSTRAINT "matches_opportunity_id_fkey" FOREIGN KEY ("opportunity_id") REFERENCES "app"."opportunities"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."runs" ADD CONSTRAINT "runs_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."runs" ADD CONSTRAINT "runs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."run_events" ADD CONSTRAINT "run_events_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "app"."runs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."applications" ADD CONSTRAINT "applications_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."applications" ADD CONSTRAINT "applications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."applications" ADD CONSTRAINT "applications_opportunity_id_fkey" FOREIGN KEY ("opportunity_id") REFERENCES "app"."opportunities"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."applications" ADD CONSTRAINT "applications_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "app"."runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."applications" ADD CONSTRAINT "applications_cv_file_id_fkey" FOREIGN KEY ("cv_file_id") REFERENCES "app"."files"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."files" ADD CONSTRAINT "files_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."usage" ADD CONSTRAINT "usage_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "app"."tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app"."usage" ADD CONSTRAINT "usage_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "app"."runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;
