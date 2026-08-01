#!/usr/bin/env node
/**
 * Bundle-size budget check for production builds.
 *
 * Reads the Next.js build manifests, sums the gzipped JavaScript each app route
 * loads on first paint, and fails when a route exceeds its budget in
 * performance-budgets.json. Run after `npm run build`.
 *
 * Requirements: 19.1, 19.7
 */

import { gzipSync } from 'node:zlib';
import { readFileSync, existsSync, statSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const frontendRoot = path.resolve(import.meta.dirname, '..');
const nextDir = path.join(frontendRoot, '.next');
const budgetsPath = path.join(frontendRoot, 'performance-budgets.json');

function fail(message) {
  console.error(`✗ ${message}`);
  process.exit(1);
}

if (!existsSync(nextDir)) {
  fail('No .next directory found. Run "npm run build" before checking bundle budgets.');
}

const budgets = JSON.parse(readFileSync(budgetsPath, 'utf8'));
const defaultBudgetKb = budgets.javascript.defaultRouteBudget;
const routeBudgetsKb = budgets.javascript.routeBudgets ?? {};

function readJsonIfPresent(file) {
  const target = path.join(nextDir, file);
  return existsSync(target) ? JSON.parse(readFileSync(target, 'utf8')) : null;
}

const appManifest = readJsonIfPresent('app-build-manifest.json');
const buildManifest = readJsonIfPresent('build-manifest.json');

if (!appManifest && !buildManifest) {
  fail('Neither app-build-manifest.json nor build-manifest.json was found in .next.');
}

const gzipCache = new Map();

function gzippedBytes(assetPath) {
  if (gzipCache.has(assetPath)) return gzipCache.get(assetPath);
  const absolute = path.join(nextDir, assetPath);
  if (!existsSync(absolute) || !statSync(absolute).isFile()) {
    gzipCache.set(assetPath, 0);
    return 0;
  }
  const size = gzipSync(readFileSync(absolute)).byteLength;
  gzipCache.set(assetPath, size);
  return size;
}

/** Map an app-router manifest key such as "/inventory/page" to a route path. */
function toRoutePath(manifestKey) {
  const withoutSegment = manifestKey.replace(/\/(page|layout|error|not-found|template)$/, '');
  const cleaned = withoutSegment.replace(/\/\([^)]*\)/g, '');
  return cleaned === '' ? '/' : cleaned;
}

const routeAssets = new Map();

if (appManifest?.pages) {
  for (const [key, assets] of Object.entries(appManifest.pages)) {
    if (!key.endsWith('/page')) continue;
    const route = toRoutePath(key);
    const existing = routeAssets.get(route) ?? new Set();
    for (const asset of assets) {
      if (asset.endsWith('.js')) existing.add(asset);
    }
    routeAssets.set(route, existing);
  }
}

if (routeAssets.size === 0 && buildManifest?.pages) {
  for (const [route, assets] of Object.entries(buildManifest.pages)) {
    const existing = new Set(assets.filter((asset) => asset.endsWith('.js')));
    routeAssets.set(route, existing);
  }
}

const sharedAssets = new Set(
  (buildManifest?.rootMainFiles ?? buildManifest?.pages?.['/_app'] ?? []).filter((asset) =>
    asset.endsWith('.js'),
  ),
);

const results = [];
for (const [route, assets] of routeAssets) {
  const all = new Set([...assets, ...sharedAssets]);
  let bytes = 0;
  for (const asset of all) bytes += gzippedBytes(asset);
  const kb = bytes / 1024;
  const budgetKb = routeBudgetsKb[route] ?? defaultBudgetKb;
  results.push({ route, kb, budgetKb, overBudget: kb > budgetKb });
}

results.sort((a, b) => b.kb - a.kb);

if (results.length === 0) {
  fail('No app routes were found in the build manifests.');
}

console.log('Route initial JavaScript (gzipped)');
console.log('---------------------------------');
for (const result of results) {
  const flag = result.overBudget ? 'OVER' : 'ok';
  console.log(
    `${result.route.padEnd(28)} ${result.kb.toFixed(1).padStart(7)} KB / ${String(result.budgetKb).padStart(4)} KB  ${flag}`,
  );
}

const violations = results.filter((result) => result.overBudget);
if (violations.length > 0) {
  console.error('');
  fail(
    `${violations.length} route(s) exceed the JavaScript budget: ${violations
      .map((violation) => `${violation.route} (${violation.kb.toFixed(1)} KB > ${violation.budgetKb} KB)`)
      .join(', ')}. Split heavy modules with dynamic imports or raise the budget only with recorded evidence.`,
  );
}

console.log('');
console.log(`✓ All ${results.length} routes are within their JavaScript budgets.`);
