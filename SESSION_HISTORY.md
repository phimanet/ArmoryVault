# Session History - FirearmsInventory

## Initial Architecture & Deployment (2026-10-11)
- Initialized dedicated FirearmsInventory service on port 8186 (`FirearmsInventory_8186` + `FirearmsInventory_api`).
- Configured data persistence with isolated `./data:/app/data` and `./uploads:/app/uploads` volumes.
- Setup Python 3.12 microservice backend with automatic 10-minute snapshot rolling backups and live code reloading.
- Integrated serial number masking toggle for discretion during display/sharing.
- Added multi-angle photo gallery, photo side-by-side comparison matrix, round counts & maintenance logs, and insurance replacement valuation reports.

## CCW Permit Compliance, Renewal Tracking & Gmail Alerts (2026-10-12)
- Added full California CCW permit compliance tracker specifically tailored for the San Diego County Sheriff's Department (SDSO).
- Added Gmail SMTP integration (`smtp.gmail.com:465`) sending responsive executive email alerts starting 120 days prior to expiration and recurring every 30 days.
- Implemented background milestone checker (`check_and_send_ccw_reminders`) and test email trigger (`POST /api/ccw/test-email`).
- Added sequential 3-step renewal milestone checklist:
  1. LiveScan fingerprinting (required before qualification class).
  2. CCW renewal class & live-fire shooting qualification.
  3. Uploading all documents and training certificates to the San Diego Sheriff (Permitium) at the critical 90-day mark before expiration.
- Added CCW permit indicators & weapon tagging:
  - Gold `🛡️ CCW` badge on cards for firearms listed on permit.
  - Spec detail indicator in popup specs grid.
  - Form checkbox toggle `🛡️ Listed on CCW Permit` when adding or editing firearms.
  - Filter bar chip `🛡️ On CCW Permit` to view all weapons authorized on the permit.
- Added comprehensive CCW management modal (`#ccwModal`) with expiration countdown, checklist tracking, and test email button.

## Alphabetical Sorting by Manufacturer & Sort Selector (2026-10-12)
- **Alphabetical Manufacturer Sorting (`server.py` & `index.html`)**:
  - Implemented automatic alphabetical sorting by Manufacturer (`make` A → Z), sub-sorted by Model (`model` A → Z).
  - Applied server-side in `handle_get_firearms()` so all API responses, scripts, and exports are sorted alphabetically.
  - Applied client-side in `fetchFirearms()` so master inventory arrays, Insurance Valuation reports, and Compare matrices inherit alphabetical Manufacturer ordering.
- **Dynamic Sort Selector Control (`index.html`)**:
  - Added responsive Sort dropdown alongside classification chips in the filter bar.
  - Supports sorting by:
    - `Manufacturer (A → Z)` *(Default)*
    - `Manufacturer (Z → A)`
    - `Model (A → Z)`
    - `Value (High to Low)`
    - `Round Count (High to Low)`
    - `Recently Updated`
  - Re-sorts filtered inventory live on change without page reloads.
- **Git Deployment Pipeline**:
  - Committed and pushed to `phimanet/FirearmsInventory` (`origin main`) for auto-deployment to `192.168.72.10:8186`.

## Interactive Photo Cropping & Framing + Round Count Cleanup (2026-10-12)
- **Interactive Photo Cropping & Framing Tool (`Cropper.js`)**:
  - Integrated local Cropper.js library (`html/js/cropper.min.js` and `cropper.min.css`) with CDN fallback for 100% offline and touch-friendly mobile/desktop operation.
  - Added dedicated `#cropPhotoModal` modal with:
    - **Aspect Ratio Presets**: `16:9 (Card Fit - Recommended)`, `3:2 (Wide)`, `4:3 (Photo)`, `1:1 (Square)`, and `Freeform`.
    - **Visual Controls**: Interactive zoom (`+` / `-`), rotation (`-90°` / `+90°`), and reset button.
    - **High-Res Canvas Export**: Crops up to 2560x2560px with high smoothing quality and uploads to `/api/upload-photo`.
  - Added `✂️ Crop Photo` button in the Detail Popout toolbar (`#detailPhotoToolbar`).
  - Added `✂️` crop icon on each thumbnail in the Add / Edit Firearm modal (`renderFormPhotos()`).
  - Automatically persists cropped photos to the firearm record on backend disk (`PUT /api/firearms/:id`).
- **Removed Round Counts from Main Page & Firearm Cards**:
  - Removed `Total Rounds Tracked` metric box from the top summary metrics banner.
  - Removed `${f.roundCount} Rds` badge from the front of all firearm inventory cards.
  - Kept detailed round count tracking and maintenance history intact inside individual firearm detail and edit modals.
- **Git Deployment Pipeline**:
  - Committed and pushed to `phimanet/FirearmsInventory` (`origin main`) and deployed to `192.168.72.10:8186`.

## Ownership Documents & DROS Vault (2026-10-12)
- **Document Storage & Upload API (`server.py`)**:
  - Configured persistent document directory `/app/uploads/documents/` (fallback `uploads/documents/`).
  - Implemented `POST /api/upload-document` endpoint supporting PDF and image uploads with auto-generation of metadata (`id`, `title`, `category`, `fileName`, `fileSize`, `fileType`, `url`, `uploadedAt`).
  - Added support for `documents` array schema in `POST /api/firearms` and `PUT /api/firearms/:id`.
- **Detail Modal Document Vault (`index.html`)**:
  - Added `🧾 Ownership Documents & DROS Vault` section to firearm popout modal.
  - Implemented responsive table with document type icons, category pills (`DROS`, `Receipt`, `Bill of Sale`, `Warranty`, `Work Order`), file size badges, upload timestamps, and direct action buttons (`👁️ View / Open`, `📥 Download`, `✕ Delete`).
  - Added quick `+ Document` button in the detail popout header allowing scanning paperwork via device camera or uploading PDFs/images directly without entering edit mode.
- **Add / Edit Modal Document Manager (`index.html`)**:
  - Added documents manager section in the firearm form modal with camera scan button, file upload button, and per-document title and category editing.
- **Git Deployment Pipeline**:
  - Committed and pushed to `phimanet/FirearmsInventory` (`origin main`) and pulled on host `192.168.72.10:8186`.
