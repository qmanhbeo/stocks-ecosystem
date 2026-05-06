---
name: tailscale-transfer
description: Send files between this machine and Manh's phone with Tailscale file transfer. Use when asked to copy, transfer, send, receive, or get a file/PDF/image/artifact over Tailscale.
---

# Tailscale Transfer

Purpose: transfer files between this machine and Manh's phone using Tailscale
Taildrop.

## Send To Phone

1. Resolve the file path.
- Use the exact file the user named.
- If the user asks for the latest dissertation PDF, use:
  `ls -t /home/manh/study-BHam/dissertation/writing/builds/dissertation_*.pdf | head -n 1`

2. Check the phone's Tailscale device name.
- Run `tailscale status`.
- Default known-good target: `iphone-14-pm`.
- If the phone name changed, use the current phone device name shown by
  `tailscale status`.

3. Send the file.
- General command:
  `tailscale file cp "<path>" iphone-14-pm:`
- Latest dissertation PDF command:
  `latest_pdf="$(ls -t /home/manh/study-BHam/dissertation/writing/builds/dissertation_*.pdf | head -n 1)"; tailscale file cp "$latest_pdf" iphone-14-pm:`

## Get From Phone

Use this when Manh has sent files from the phone to this machine through
Tailscale.

1. Pick the correct destination for the current task.
- If working inside a project, choose the folder where the files should actually
  live, not a random download location.
- Example: for a website image in `qmanhbeosite`, prompt Manh to receive into
  the appropriate `public/img/` or equivalent asset folder.

2. Because the receive command uses `sudo`, prompt Manh to run it manually with
the chosen destination directory from root.
- Preferred pattern:
  `sudo tailscale file get "<absolute-destination-dir>"`
- Example:
  `sudo tailscale file get /home/manh/qmanhbeosite/public/img`
- If the correct holding folder is `tailscale-get`, use its absolute path, for
  example `sudo tailscale file get /home/manh/<project>/tailscale-get`.
- Do not run the sudo receive command silently or choose a destination without
  considering the current project structure.

## Notes

- The phone must be online in the same tailnet.
- Received files appear in the iOS Files app under the Tailscale transfer
  location.
- If transfer fails, re-check `tailscale status`, confirm the file exists, and
  retry with the exact device name from status.
