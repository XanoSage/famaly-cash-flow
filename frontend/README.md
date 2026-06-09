# Frontend

React + Vite + TypeScript frontend for Family Cash Flow.

## Local Commands

```bash
npm install
npm run dev
npm run build
```

On Windows PowerShell, if `npm` is blocked by execution policy, use `npm.cmd`:

```powershell
npm.cmd install
npm.cmd run dev
npm.cmd run build
```

Run the dev server explicitly on the local Vite port:

```powershell
cd E:\Work\Codex\FamilyCashFlow\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Keep that terminal open while using the app:

```text
http://127.0.0.1:5173/
```

If `npm install` fails with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, Node does not trust the
certificate chain used for the npm registry. Use the Windows system certificate store:

```powershell
$env:NODE_OPTIONS='--use-system-ca'
npm.cmd install
```

### Codex/Vite process note

During local verification on Windows, `npm run dev` started Vite correctly in the
foreground, but the Codex command timeout stopped the process after the readiness check.
Attempts to detach it through `Start-Process npm.cmd` and `cmd.exe /c npm.cmd run dev`
did not leave a stable listener on port `5173`.

The working detached launch used Node directly with Vite's installed entrypoint:

```powershell
Start-Process `
  -FilePath 'C:\Program Files\nodejs\node.exe' `
  -ArgumentList @(
    'E:\Work\Codex\FamilyCashFlow\frontend\node_modules\vite\bin\vite.js',
    '--host',
    '127.0.0.1',
    '--port',
    '5173'
  ) `
  -WorkingDirectory 'E:\Work\Codex\FamilyCashFlow\frontend' `
  -WindowStyle Hidden
```

Check that it is listening:

```powershell
netstat -ano | Select-String ':5173'
```

## API

By default the app calls:

```bash
http://localhost:8000/api/v1
```

Override it for another backend:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

For the MVP dashboard, paste a `family_id` from the database/imported data into the filter bar.

