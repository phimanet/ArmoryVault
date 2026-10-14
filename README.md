# Armory Vault - Executive Firearms & CCW Asset Management

Armory Vault is a secure, responsive offline-first firearm asset management, compliance tracking, and valuation platform running within the `DockerMonsterWebServer` microservice topology.

---

## Key Features

- **Inventory & Build Matrix**: Complete management of handguns, rifles, shotguns, suppressors/NFA items, mounted optics, lights, and weapon build accessories.
- **Photo Studio & High-Res Cropping**: Multi-photo gallery, integrated Cropper.js framing tool (16:9, 3:2, 4:3, 1:1, Freeform), image rotation, and serial OCR scanner.
- **Ownership Documents & DROS Vault**: PDF and photo storage for California DOJ DROS paperwork, dealer purchase receipts, bills of sale, and manufacturer warranty cards.
- **CCW Compliance & Gmail Alerts**: San Diego County Sheriff's Department (SDSO) renewal milestone tracker (LiveScan, class qualification, 90-day CCW Pro submission) with automated SSL SMTP email alerts.
- **Insurance Valuation Reports**: One-click insurance asset schedule generation with categorized valuation totals, serialized build breakdowns, and print/export formatting.
- **Privacy & Security**: Instant serial number masking toggle for discreet display, RFC1918 local LAN & Tailscale CGNAT CORS security, and zero cloud dependency.
- **Data Persistence**: Dedicated `./data` and `./uploads` volume mounts with automated rolling snapshots every 10 minutes and on-demand UI snapshots.

---

## Architecture & Ports

- **Port**: `8186` mapped to port 80 (Nginx Alpine)
- **API**: Internal Python 3.12 Alpine microservice on port 5000 (`/api/`)
- **Live URL**: `http://192.168.72.10:8186`
- **Local Directory**: `/home/phimane/Documents/GitHub/DockerMonsterWebServer/ArmoryVault`
- **Host Directory**: `/docker/ArmoryVault`

---

## Running Locally

```bash
docker compose up -d
```
Access at `http://localhost:8186` or LAN IP.
