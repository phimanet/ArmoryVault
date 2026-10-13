# ArmoryVault - Project Rules & Architecture
> Inherits all global workspace rules, security posture, and operating principles from [../GEMINI.md](../GEMINI.md).

## Project Specifications & Repository
- **Dedicated Repository**: `https://github.com/phimanet/ArmoryVault.git` on branch `main`.
- **Local Directory**: `/home/phimane/Documents/GitHub/DockerMonsterWebServer/ArmoryVault`
- **Host Directory**: `/docker/ArmoryVault`
- **Live URL**: `http://192.168.72.10:8186`

## Universal Data Persistence & Anti-Data-Loss Rule
- **Isolated Storage Volumes**: All database records (`/docker/ArmoryVault/data/firearms.json`) and uploaded media (`/docker/ArmoryVault/uploads/photos/`, `/docker/ArmoryVault/uploads/documents/`) **MUST ALWAYS** live in dedicated root host directories `./data:/app/data` and `./uploads:/app/uploads`.
- **Git Separation**: `./data` and `./uploads` are strictly excluded from `.gitignore`. Git pulls, code changes, or web page updates MUST NEVER overwrite, erase, or reset user data, receipts, or photos.
- **Auto-Save & Snapshot Rule**:
  - The backend runs automated rolling database snapshots every 10 minutes (`/data/backups/firearms_YYYYMMDD_HHMMSS.json`).
  - The UI features an explicit **Save / Snapshot** button in the header for on-demand persistent snapshots.
  - Data must survive server reboots, container recreations, Docker updates, and code pushes.
- **1-Click Full Archive Export (`.zip`) & Rebuild Portability**:
  - The backend microservice implements `GET /api/export-archive` bundling all firearm records (`database/firearms.json`), weapon photos (`photos/`), and DROS/receipt documents (`documents/`) into a single ZIP with an export manifest.
  - The UI features an explicit **`📦 Export Archive`** button in the header for 1-click download and off-site cloud backup (Google Drive).
  - In the event of a system rebuild or migration, the vault must be fully restorable from the exported archive.

## Privacy & Security Posture
- **Serial Privacy Masking**: Serial numbers must be masked by default in the UI (`••••••••` / `***-***-1234`) with a quick global toggle or per-item unmask icon for discreet screen viewing and screenshots.
- **RFC1918 / Localhost CORS**: Strict origin checking restricting API access to local LAN and Tailscale CGNAT subnets.
- **Attachment & Asset Security**: Dotfiles and raw database files blocked by Nginx reverse proxy.

## Container Topology & Microservice Architecture
- **Web Server Container**: `ArmoryVault_8186` (Nginx Alpine)
  - Port: `8186` mapped to port 80
  - Mounts:
    - `./html:/usr/share/nginx/html:ro`
    - `./uploads:/usr/share/nginx/uploads:ro`
    - `./nginx.conf:/etc/nginx/conf.d/default.conf:ro`
  - Reverse Proxy: `/api/` proxies to internal backend container `http://api:5000`
  - Upload Limit: `client_max_body_size 25M;`
- **Backend Container**: `ArmoryVault_api` (Python 3.12 Alpine)
  - Mounts:
    - `./html:/app/html:ro`
    - `./data:/app/data` (Persistent Read-Write)
    - `./uploads:/app/uploads` (Persistent Read-Write)
    - `./.env:/app/.env:ro`
  - Features: Automatic process reload watcher on file change, automated 10-minute snapshot backups, Gmail SMTP CCW alerts, and secure REST endpoints.
