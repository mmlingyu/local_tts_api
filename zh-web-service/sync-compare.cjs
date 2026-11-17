const fs = require('node:fs');
const path = require('node:path');

const root = __dirname;
const source = path.resolve(root, '..', 'piper-zh-service', 'static');
const dest = path.join(root, 'public');
const files = {
  'compare.html': 'piper-compare.html',
  'compare.js': 'piper-compare.js',
  'compare.css': 'piper-compare.css',
  'compare-logic.mjs': 'piper-compare-logic.mjs',
};

function syncCompare() {
  if (!fs.existsSync(source)) {
    const missing = Object.values(files).filter((name) => !fs.existsSync(path.join(dest, name)));
    if (missing.length) {
      throw new Error('缺少对照页文件，且找不到 ../piper-zh-service/static：' + missing.join(', '));
    }
    return 'kept-public-copies';
  }
  fs.mkdirSync(dest, { recursive: true });
  for (const [from, to] of Object.entries(files)) {
    fs.copyFileSync(path.join(source, from), path.join(dest, to));
  }
  return 'copied';
}

if (require.main === module) {
  try {
    console.log(syncCompare());
  } catch (error) {
    console.error(error.message || error);
    process.exit(1);
  }
}

module.exports = syncCompare;
