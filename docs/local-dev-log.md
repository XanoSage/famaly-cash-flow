# Local Dev Log

## 2026-06-08 - Vite dev server on Windows

What happened:

- `npm install` first failed in PowerShell because `npm.ps1` was blocked by the Windows execution policy.
- Using `npm.cmd` bypassed the PowerShell script policy.
- `npm install` then failed with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`; running it with `NODE_OPTIONS=--use-system-ca` fixed npm certificate verification by using the Windows certificate store.
- `npm.cmd run dev -- --host 127.0.0.1 --port 5173` started Vite correctly in the foreground.
- In Codex, the command timeout stopped the foreground process after Vite printed its ready message.
- Detached launches through `Start-Process npm.cmd` and `cmd.exe /c npm.cmd run dev` did not leave a stable listener on `127.0.0.1:5173`.
- The stable detached launch used Node directly with Vite's local entrypoint.

Stable detached launch used by Codex:

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

Recommended manual command:

```powershell
cd E:\Work\Codex\FamilyCashFlow\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Keep the terminal open, then open:

```text
http://127.0.0.1:5173/
```

Check the port:

```powershell
netstat -ano | Select-String ':5173'
```
