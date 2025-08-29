#!/usr/bin/env node

/**
 * UI Guard Script
 * Forbids sidebar components in the codebase
 */

const fs = require('fs');
const path = require('path');
const glob = require('glob');

// Patterns to detect sidebars
const FORBIDDEN_PATTERNS = [
  /\bSidebar\b/i,
  /\bsidenav\b/i,
  /\bdrawer\b/i,
  /\bLeftMenu\b/i,
  /\bRightMenu\b/i,
  /\bleft-panel\b/i,
  /\bright-panel\b/i,
  /\bside-menu\b/i,
  /\bnavigation-drawer\b/i,
  /\blayout-sidebar\b/i,
  /data-sidebar/i,
  /className=["'].*sidebar/i,
  /id=["'].*sidebar/i,
];

// File extensions to check
const FILE_EXTENSIONS = [
  '**/*.tsx',
  '**/*.ts',
  '**/*.jsx',
  '**/*.js',
  '**/*.html',
  '**/*.css',
  '**/*.scss',
];

// Directories to exclude
const EXCLUDE_DIRS = [
  'node_modules',
  'dist',
  'build',
  '.git',
  'coverage',
  '.next',
  'scripts/ui-guard.js', // Exclude this file
];

function checkFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const violations = [];
  const lines = content.split('\n');

  lines.forEach((line, index) => {
    FORBIDDEN_PATTERNS.forEach((pattern) => {
      if (pattern.test(line)) {
        violations.push({
          file: filePath,
          line: index + 1,
          pattern: pattern.toString(),
          content: line.trim(),
        });
      }
    });
  });

  return violations;
}

function main() {
  console.log('🔍 UI Guard: Checking for forbidden sidebar components...\n');

  let allViolations = [];
  let filesChecked = 0;

  // Check each file type
  FILE_EXTENSIONS.forEach((pattern) => {
    const files = glob.sync(pattern, {
      ignore: EXCLUDE_DIRS.map(dir => `**/${dir}/**`),
      nodir: true,
    });

    files.forEach((file) => {
      filesChecked++;
      const violations = checkFile(file);
      if (violations.length > 0) {
        allViolations = allViolations.concat(violations);
      }
    });
  });

  // Report results
  console.log(`📊 Checked ${filesChecked} files\n`);

  if (allViolations.length > 0) {
    console.error('❌ FORBIDDEN SIDEBAR COMPONENTS DETECTED!\n');
    console.error('The following violations were found:\n');

    // Group violations by file
    const violationsByFile = {};
    allViolations.forEach((violation) => {
      if (!violationsByFile[violation.file]) {
        violationsByFile[violation.file] = [];
      }
      violationsByFile[violation.file].push(violation);
    });

    // Print violations
    Object.keys(violationsByFile).forEach((file) => {
      console.error(`📄 ${file}:`);
      violationsByFile[file].forEach((violation) => {
        console.error(`   Line ${violation.line}: ${violation.content}`);
        console.error(`   Pattern: ${violation.pattern}\n`);
      });
    });

    console.error('\n🚫 UI Guard check failed!');
    console.error('Remove all sidebar components and use AppShell with navbar-only layout.\n');
    process.exit(1);
  } else {
    console.log('✅ No sidebar components detected!');
    console.log('All files comply with the navbar-only layout requirement.\n');
    process.exit(0);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

module.exports = { checkFile, FORBIDDEN_PATTERNS };