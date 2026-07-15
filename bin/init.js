#!/usr/bin/env node

'use strict';

/*
 * sdd-toolkit — Moova's Spec-Driven Development toolkit installer.
 *
 * Commands:
 *   sdd init   [target]  [--agents=claude] [--tickets=jira]   Scaffold SDD assets into a repo (first time).
 *   sdd update [target]  [--dry-run]                          Refresh managed assets to the latest toolkit version.
 *   sdd help                                                   Show usage.
 *
 * Model:
 *   - "managed" assets (agents, skills, commands) are the toolkit's property. They live in `ai-specs/`
 *     inside the target repo and are OVERWRITTEN on `update`. Tool dirs like `.claude/` are symlinks
 *     into `ai-specs/`, so updating the real file updates what every agent tool sees.
 *   - "scaffold" files (openspec/config.yaml, ...) are copied ONCE and never overwritten — each repo owns them.
 *   - `.sdd-toolkit.json` records the applied version and the chosen agents / ticket system.
 */

const fs = require('fs');
const path = require('path');

const PKG = require(path.join(__dirname, '..', 'package.json'));
const TEMPLATE_DIR = path.join(__dirname, '..', 'template');
const AI_SPECS_SRC = path.join(TEMPLATE_DIR, 'ai-specs');
const SCAFFOLD_SRC = path.join(TEMPLATE_DIR, 'scaffold');
const TICKETS_SRC = path.join(AI_SPECS_SRC, 'tickets');
const CONFIG_FILE = '.sdd-toolkit.json';

// Managed categories: top-level dirs under ai-specs/ that get copied verbatim and symlinked into tool dirs.
const MANAGED_CATEGORIES = ['agents', 'skills', 'commands'];

// Agent tool registry: name -> where to materialize symlinks and which categories it consumes.
// Adding a new tool is config-only for consumers; adding its mapping here enables it.
const AGENT_TOOLS = {
  claude: { dir: '.claude', categories: ['agents', 'skills', 'commands'] },
};

// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const flags = {};
  const positional = [];
  for (const a of argv) {
    if (a.startsWith('--')) {
      const [k, v] = a.slice(2).split('=');
      flags[k] = v === undefined ? true : v;
    } else {
      positional.push(a);
    }
  }
  return { flags, positional };
}

function pathExists(p) {
  try { fs.lstatSync(p); return true; } catch { return false; }
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readConfig(target) {
  const p = path.join(target, CONFIG_FILE);
  if (!pathExists(p)) return null;
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return null; }
}

function writeConfig(target, config) {
  fs.writeFileSync(path.join(target, CONFIG_FILE), JSON.stringify(config, null, 2) + '\n');
}

// List files recursively, returning paths relative to `root`.
function listFiles(root) {
  const out = [];
  if (!pathExists(root)) return out;
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (entry.name === '.DS_Store') continue;
    const abs = path.join(root, entry.name);
    if (entry.isDirectory()) {
      for (const rel of listFiles(abs)) out.push(path.join(entry.name, rel));
    } else {
      out.push(entry.name);
    }
  }
  return out;
}

function sameContent(a, b) {
  if (!pathExists(a) || !pathExists(b)) return false;
  return fs.readFileSync(a).equals(fs.readFileSync(b));
}

// ---------------------------------------------------------------------------
// Managed assets

// Build the list of managed source files: {srcAbs, rel} where rel is relative to ai-specs/,
// plus the resolved ticket template for the chosen system.
function managedSources(ticketSystem) {
  const items = [];
  for (const cat of MANAGED_CATEGORIES) {
    const catRoot = path.join(AI_SPECS_SRC, cat);
    for (const rel of listFiles(catRoot)) {
      items.push({ srcAbs: path.join(catRoot, rel), rel: path.join(cat, rel) });
    }
  }
  // Ticket template resolves to a system-neutral path the commands reference.
  const ticketSrc = path.join(TICKETS_SRC, ticketSystem, 'ticket-template.md');
  if (pathExists(ticketSrc)) {
    items.push({ srcAbs: ticketSrc, rel: 'ticket-template.md' });
  }
  return items;
}

// Copy managed files into target/ai-specs/, overwriting. Returns {added, updated, unchanged}.
function applyManaged(target, ticketSystem, { dryRun }) {
  const stats = { added: [], updated: [], unchanged: [] };
  for (const { srcAbs, rel } of managedSources(ticketSystem)) {
    const destAbs = path.join(target, 'ai-specs', rel);
    if (!pathExists(destAbs)) {
      stats.added.push(rel);
    } else if (!sameContent(srcAbs, destAbs)) {
      stats.updated.push(rel);
    } else {
      stats.unchanged.push(rel);
      continue;
    }
    if (!dryRun) {
      ensureDir(path.dirname(destAbs));
      fs.copyFileSync(srcAbs, destAbs);
    }
  }
  return stats;
}

// ---------------------------------------------------------------------------
// Scaffold (copy-once)

function applyScaffold(target, { dryRun }) {
  const stats = { copied: [], skipped: [] };
  for (const rel of listFiles(SCAFFOLD_SRC)) {
    const srcAbs = path.join(SCAFFOLD_SRC, rel);
    const destAbs = path.join(target, rel);
    if (pathExists(destAbs)) {
      stats.skipped.push(rel);
      continue;
    }
    stats.copied.push(rel);
    if (!dryRun) {
      ensureDir(path.dirname(destAbs));
      fs.copyFileSync(srcAbs, destAbs);
    }
  }
  return stats;
}

// ---------------------------------------------------------------------------
// Symlinks: tool dirs (.claude/...) point back into ai-specs/.

function ensureSymlinks(target, agents, { dryRun }) {
  const stats = { linked: [], existing: [], errors: [] };
  for (const agent of agents) {
    const tool = AGENT_TOOLS[agent];
    if (!tool) {
      stats.errors.push(`unknown agent tool "${agent}" (no mapping)`);
      continue;
    }
    for (const cat of tool.categories) {
      const catRoot = path.join(AI_SPECS_SRC, cat);
      if (!pathExists(catRoot)) continue;
      // Symlink each top-level entry (file or dir) of the category.
      for (const entry of fs.readdirSync(catRoot, { withFileTypes: true })) {
        if (entry.name === '.DS_Store' || entry.name === 'tickets') continue;
        const linkPath = path.join(target, tool.dir, cat, entry.name);
        // From <tool>/<cat>/<entry>, repo root is two levels up.
        const linkTarget = path.join('..', '..', 'ai-specs', cat, entry.name);
        if (pathExists(linkPath)) {
          stats.existing.push(path.join(tool.dir, cat, entry.name));
          continue;
        }
        stats.linked.push(`${path.join(tool.dir, cat, entry.name)} -> ${linkTarget}`);
        if (!dryRun) {
          try {
            ensureDir(path.dirname(linkPath));
            fs.symlinkSync(linkTarget, linkPath);
          } catch (err) {
            stats.errors.push(`${path.join(tool.dir, cat, entry.name)}: ${err.message}`);
          }
        }
      }
    }
  }
  return stats;
}

// ---------------------------------------------------------------------------

function resolveTarget(positional) {
  return positional[0] ? path.resolve(positional[0]) : process.cwd();
}

function banner(target) {
  console.log(`\n  sdd-toolkit v${PKG.version}`);
  console.log('  Moova Spec-Driven Development toolkit\n');
  console.log(`  Target: ${target}\n`);
}

function cmdInit(flags, positional) {
  const target = resolveTarget(positional);
  banner(target);

  const existing = readConfig(target) || {};
  const agents = (flags.agents ? String(flags.agents).split(',') : existing.agents) || ['claude'];
  const ticketSystem = flags.tickets || existing.ticketSystem || 'jira';

  if (!pathExists(path.join(TICKETS_SRC, ticketSystem))) {
    console.error(`  ! Unknown ticket system "${ticketSystem}". Available: ${fs.readdirSync(TICKETS_SRC).join(', ')}\n`);
    process.exit(1);
  }

  const managed = applyManaged(target, ticketSystem, { dryRun: false });
  const scaffold = applyScaffold(target, { dryRun: false });
  const links = ensureSymlinks(target, agents, { dryRun: false });

  writeConfig(target, { version: PKG.version, agents, ticketSystem });

  console.log(`  Agents        ${agents.join(', ')}`);
  console.log(`  Tickets       ${ticketSystem}`);
  console.log(`  Managed       ${managed.added.length} added, ${managed.updated.length} updated`);
  console.log(`  Scaffold      ${scaffold.copied.length} copied, ${scaffold.skipped.length} skipped`);
  console.log(`  Symlinks      ${links.linked.length} created, ${links.existing.length} existing`);
  if (links.errors.length) {
    console.log(`\n  Errors (${links.errors.length}):`);
    for (const e of links.errors) console.log(`    ! ${e}`);
  }
  console.log('\n  Next steps:');
  console.log('  1. Fill openspec/config.yaml (project context) and run `openspec init` if needed');
  console.log('  2. Commit ai-specs/, .claude/ and .sdd-toolkit.json');
  console.log('  3. Use /implement, /opsx:propose, /opsx:apply\n');
}

function cmdUpdate(flags, positional) {
  const target = resolveTarget(positional);
  const dryRun = !!flags['dry-run'];
  banner(target);

  const config = readConfig(target);
  if (!config) {
    console.error(`  ! No ${CONFIG_FILE} found. Run \`sdd init\` first.\n`);
    process.exit(1);
  }
  const agents = config.agents || ['claude'];
  const ticketSystem = config.ticketSystem || 'jira';

  const managed = applyManaged(target, ticketSystem, { dryRun });
  const links = ensureSymlinks(target, agents, { dryRun });

  console.log(`  ${dryRun ? '[dry-run] ' : ''}Version       ${config.version} -> ${PKG.version}`);
  console.log(`  Agents        ${agents.join(', ')}`);
  console.log(`  Tickets       ${ticketSystem}\n`);

  const show = (label, list) => {
    if (!list.length) return;
    console.log(`  ${label} (${list.length}):`);
    for (const x of list) console.log(`    ${x}`);
  };
  show('Added', managed.added);
  show('Updated', managed.updated);
  show('New symlinks', links.linked);
  console.log(`\n  ${managed.unchanged.length} file(s) already up to date.`);

  if (dryRun) {
    console.log('\n  Dry run — no files written.\n');
    return;
  }
  writeConfig(target, { ...config, version: PKG.version, agents, ticketSystem });
  if (links.errors.length) {
    console.log(`\n  Errors (${links.errors.length}):`);
    for (const e of links.errors) console.log(`    ! ${e}`);
  }
  console.log('\n  Done. Review the diff and commit.\n');
}

function cmdHelp() {
  console.log(`
  sdd-toolkit v${PKG.version} — Moova Spec-Driven Development toolkit

  Usage:
    sdd init   [target] [--agents=claude] [--tickets=jira]   Scaffold SDD assets into a repo (run once).
    sdd update [target] [--dry-run]                          Refresh managed assets to this toolkit version.
    sdd help                                                  Show this help.

  Managed assets (agents / skills / commands) live in ai-specs/ and are refreshed by \`update\`.
  Scaffold files (openspec/config.yaml) are copied once and never overwritten.
  Tool dirs (.claude/) are symlinks into ai-specs/. Config is stored in ${CONFIG_FILE}.
`);
}

function main() {
  const [cmd, ...rest] = process.argv.slice(2);
  const { flags, positional } = parseArgs(rest);
  switch (cmd) {
    case 'init': return cmdInit(flags, positional);
    case 'update': return cmdUpdate(flags, positional);
    case 'help': case '--help': case '-h': case undefined: return cmdHelp();
    default:
      console.error(`Unknown command "${cmd}". Run \`sdd help\`.`);
      process.exit(1);
  }
}

main();
