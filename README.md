# EEI Explorer

REST API for querying the [Landler EEI Global Dataset](https://landler.io/) on Google Earth Engine. Given a polygon or bounding box it returns mean values of four ecosystem integrity bands at 300 m resolution.

---

## Prerequisites

- Python 3.9+
- A Google Cloud project with the **Earth Engine API** enabled
- A GEE-registered service account (see below)

---

## Google Earth Engine setup

### 1. Create a Google Cloud project

Go to [console.cloud.google.com](https://console.cloud.google.com), create a project, and note the **Project ID**.

### 2. Enable the Earth Engine API

In the Cloud Console navigate to **APIs & Services → Library**, search for *Google Earth Engine API*, and click **Enable**.

### 3. Register the project with Earth Engine

Visit [code.earthengine.google.com/register](https://code.earthengine.google.com/register) and register your Cloud project for Earth Engine access.

### 4. Create a service account

1. Go to **IAM & Admin → Service Accounts** in the Cloud Console.
2. Click **Create Service Account**, give it a name (e.g. `eei-explorer`).
3. Grant the role **Earth Engine Resource Viewer** (or a broader role if you need write access).
4. Click **Done**.

### 5. Create and download a JSON key

1. Click the service account you just created.
2. Go to the **Keys** tab → **Add Key → Create new key → JSON**.
3. Save the downloaded file — you will pass its contents as an environment variable.

### 6. Register the service account with Earth Engine

Run once (requires the `earthengine` CLI or can be done via the EE Code Editor):

```bash
earthengine acl set-service-account-quota \
  --project YOUR_PROJECT_ID \
  your-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Or visit [signup.earthengine.google.com](https://signup.earthengine.google.com) and register the service account email.

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Configuration

Set two environment variables before starting the server:

| Variable | Description |
|---|---|
| `GEE_SERVICE_ACCOUNT_KEY` | Full contents of the service account JSON key file |
| `GEE_PROJECT_ID` | Your Google Cloud project ID |

### Example (Linux / macOS)

```bash
export GEE_SERVICE_ACCOUNT_KEY=$(cat /path/to/key.json)
export GEE_PROJECT_ID=my-gee-project
```

### Example (Windows PowerShell)

```powershell
$env:GEE_SERVICE_ACCOUNT_KEY = Get-Content key.json -Raw
$env:GEE_PROJECT_ID = "my-gee-project"
```

### Example (.env file with python-dotenv)

```
GEE_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"..."}
GEE_PROJECT_ID=my-gee-project
```

---

## Running

```bash
python app.py
```

The server starts on port **5000** by default. Override with the `PORT` environment variable.

Visit [http://localhost:5000](http://localhost:5000) for the landing page.

---

## Demo mode

If `GEE_SERVICE_ACCOUNT_KEY` or `GEE_PROJECT_ID` are absent the app runs in **demo mode**: it returns latitude-based estimates instead of real GEE values. All demo responses include `"demo_mode": true`.

---

## API

### `GET /`

HTML landing page showing API status and usage examples.

### `GET /health`

```json
{"status": "ok", "gee_ready": true}
```

### `POST /api/query`

Query mean EII values for a region.

**Request body — bounding box:**

```json
{
  "bbox": [-2.5, 51.3, -2.0, 51.6]
}
```

`[minLon, minLat, maxLon, maxLat]` in decimal degrees (WGS-84).

**Request body — GeoJSON geometry:**

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[
      [-2.5, 51.3], [-2.0, 51.3],
      [-2.0, 51.6], [-2.5, 51.6],
      [-2.5, 51.3]
    ]]
  }
}
```

A GeoJSON `Feature` (with a `geometry` property) is also accepted.

**Response:**

```json
{
  "eii": 0.4821,
  "functional_integrity": 0.4663,
  "structural_integrity": 0.5104,
  "compositional_integrity": 0.4739
}
```

All values are on a **0–1** scale. `null` means no valid pixels were found in the region.

| Band | Description |
|---|---|
| `eii` | Overall Ecosystem Integrity Index |
| `functional_integrity` | Ecosystem function and process integrity |
| `structural_integrity` | Habitat structure and connectivity |
| `compositional_integrity` | Species composition integrity |

---

## Dataset

- **GEE asset:** `projects/landler-open-data/assets/eii/global/eii_global_v1`
- **Resolution:** 300 m
- **Coverage:** Global
- **Scale:** 0–1 (higher = more intact)
- **Provider:** [Landler](https://landler.io/)
