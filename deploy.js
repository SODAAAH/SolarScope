const { execSync } = require('child_process');

function run(cmd) {
  execSync(cmd, { stdio: 'inherit' });
}

try {
  run('git add backend/app/security/auth.py backend/app/storage/blob_sync.py frontend/src/components/layout/AppShell.tsx frontend/src/pages/HistoricalLibraryPage.tsx frontend/src/pages/SettingsPage.tsx deploy.js');
  try {
    run('git commit -m "Persist settings and imported files in account across restarts"');
  } catch (e) {}
  run('git push origin main');
  run('vercel deploy --prod --yes');
} catch (err) {
  process.exit(1);
}
