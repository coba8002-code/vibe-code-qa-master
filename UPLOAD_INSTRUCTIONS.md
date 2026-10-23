# QA MASTER v9 upload

The repository is initialized. Upload the reviewed v9 source package before enabling CI. Do not upload ZIP archives, `.env`, credentials, databases, or build outputs.

On Windows, extract `vibe-qa-master-release-candidate-v9.zip`. Open PowerShell in the extracted `vibe-qa-master` directory:

```powershell
git init
git remote add origin https://github.com/coba8002-code/vibe-code-qa-master.git
git fetch origin main
git checkout -b main --track origin/main
git add .
git commit -m "feat: import QA MASTER v9 source"
git push origin main
```

If `git checkout` refuses because of untracked files, clone the repository into a new folder and copy the extracted source into it, then `git add`, `git commit`, `git push`.

After upload, run Actions > Build Windows installer (manual) > Run workflow. Download the unsigned installer artifact only after the Windows smoke and installation checks pass. Never run untrusted projects outside a sandbox.
