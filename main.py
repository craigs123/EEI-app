import os
import json
import math
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import ee

app = Flask(__name__, static_folder='static', template_folder='templates')

# Enable CORS for all routes - allows other apps to call this API
CORS(app)

# EEI Asset path
EEI_ASSET_PATH = "projects/landler-open-data/assets/eii/global/eii_global_v1"

# Maximum coordinates accepted by /api/eei-batch in a single request. Each
# coordinate is a separate Earth Engine round-trip, so this bounds request
# latency. Requests above this are not rejected — they fall back gracefully
# to the first MAX_BATCH_COORDINATES points (see eei_batch).
MAX_BATCH_COORDINATES = 100

# Initialize Earth Engine
ee_initialized = False

ee_init_attempted = False
ee_init_error = None

def initialize_ee():
    """Initialize Google Earth Engine with service account or default credentials."""
    global ee_initialized, ee_init_attempted, ee_init_error
    
    if ee_initialized:
        return True
    
    if ee_init_attempted:
        # Already tried and failed, don't retry
        return False
    
    ee_init_attempted = True
    
    # Check for service account credentials in environment
    service_account_key = os.environ.get('GEE_SERVICE_ACCOUNT_KEY', '').strip()
    project_id = os.environ.get('GEE_PROJECT_ID', '').strip()

    # If no key is supplied directly, fall back to Secret Manager. This keeps
    # the service account JSON out of app.yaml so the config can be committed.
    if not service_account_key:
        secret_id = os.environ.get('GEE_SECRET_ID', '').strip()
        if secret_id and project_id:
            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
                service_account_key = client.access_secret_version(
                    name=name
                ).payload.data.decode('utf-8').strip()
                print(f"Loaded GEE service account key from Secret Manager: {secret_id}")
            except Exception as e:
                ee_init_error = f"Failed to load key from Secret Manager: {e}"
                print(ee_init_error)

    if service_account_key and project_id:
        try:
            from google.oauth2 import service_account as sa_module
            import base64
            # Accept either raw JSON or base64-encoded JSON
            if not service_account_key.startswith('{'):
                service_account_key = base64.b64decode(service_account_key).decode('utf-8')
            key_data = json.loads(service_account_key)
            credentials = sa_module.Credentials.from_service_account_info(
                key_data,
                scopes=["https://www.googleapis.com/auth/earthengine"],
            )
            print(f"Attempting to initialize Earth Engine with: {key_data.get('client_email')}")
            ee.Initialize(credentials=credentials, project=project_id)
            ee_initialized = True
            print("Earth Engine initialized successfully with service account!")
            return True
        except json.JSONDecodeError as e:
            ee_init_error = f"Invalid JSON in service account key: {e}"
            print(ee_init_error)
        except Exception as e:
            ee_init_error = f"Service account init failed: {e}"
            print(ee_init_error)
            if "not registered" in str(e).lower():
                print("NOTE: You need to register your service account at:")
                print("https://signup.earthengine.google.com/#!/service_accounts")
    
    # Fallback: try default credentials
    try:
        ee.Initialize(project=project_id or 'ee-landler-open-data')
        ee_initialized = True
        print("Earth Engine initialized with default credentials")
        return True
    except Exception as e1:
        try:
            ee.Initialize()
            ee_initialized = True
            print("Earth Engine initialized (default)")
            return True
        except Exception as e2:
            ee_init_error = f"All initialization methods failed: {e2}"
            print(ee_init_error)
            return False


def get_eei_stats_from_gee(latitude: float, longitude: float) -> dict:
    """
    Get EEI statistics from Google Earth Engine for a given point.
    Uses the public Landler EEI asset.
    """
    if not initialize_ee():
        return {
            "error": "Google Earth Engine not initialized. Please set up authentication.",
            "setup_instructions": "Run 'earthengine authenticate' in terminal or set up a service account."
        }
    
    try:
        # Create point geometry
        point = ee.Geometry.Point([longitude, latitude])
        
        # Load the EEI image
        eii_image = ee.Image(EEI_ASSET_PATH)
        
        # Sample the image at the point location
        sample = eii_image.sample(region=point, scale=300, numPixels=1).first()
        
        # Get the values
        values = sample.getInfo()
        
        if values is None:
            return {
                "geometry_type": "Point",
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "values": {
                    "eii": None,
                    "functional_integrity": None,
                    "structural_integrity": None,
                    "compositional_integrity": None
                },
                "message": "No data available for this location (likely ocean or data gap)"
            }
        
        properties = values.get('properties', {})
        
        return {
            "geometry_type": "Point",
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "values": {
                "eii": properties.get('eii') or properties.get('EII') or properties.get('b1'),
                "functional_integrity": properties.get('functional_integrity') or properties.get('functional') or properties.get('b2'),
                "structural_integrity": properties.get('structural_integrity') or properties.get('structural') or properties.get('b3'),
                "compositional_integrity": properties.get('compositional_integrity') or properties.get('compositional') or properties.get('b4')
            },
            "source": "Google Earth Engine - Landler Open Data"
        }
        
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
            return {
                "error": "EEI asset not accessible. The asset may require authentication.",
                "details": error_msg
            }
        return {
            "error": f"Error fetching EEI data: {error_msg}"
        }


def get_eei_stats_demo(latitude: float, longitude: float) -> dict:
    """
    Demo mode: Return realistic EEI estimates based on biome patterns.
    Used when Google Earth Engine is not available.
    """
    import math
    
    # Simple land/ocean detection
    is_ocean = True
    land_areas = [
        {"lat": (25, 85), "lon": (-170, -50)},   # North America
        {"lat": (-55, 15), "lon": (-85, -35)},   # South America
        {"lat": (35, 75), "lon": (-25, 60)},     # Europe
        {"lat": (-35, 38), "lon": (-20, 55)},    # Africa
        {"lat": (5, 80), "lon": (25, 180)},      # Asia
        {"lat": (-45, -10), "lon": (110, 155)},  # Australia
    ]
    
    for area in land_areas:
        if area["lat"][0] <= latitude <= area["lat"][1] and area["lon"][0] <= longitude <= area["lon"][1]:
            is_ocean = False
            break
    
    if is_ocean:
        return {
            "geometry_type": "Point",
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "values": {
                "eii": None,
                "functional_integrity": None,
                "structural_integrity": None,
                "compositional_integrity": None
            },
            "message": "EEI data is only available for terrestrial ecosystems",
            "demo_mode": True
        }
    
    # Generate realistic values based on latitude/biome
    abs_lat = abs(latitude)
    if abs_lat < 23:  # Tropical
        base_eii = 0.65
    elif abs_lat < 35:  # Subtropical
        base_eii = 0.45
    elif abs_lat < 55:  # Temperate
        base_eii = 0.50
    elif abs_lat < 66:  # Boreal
        base_eii = 0.60
    else:  # Polar
        base_eii = 0.55
    
    # Add geographic variation
    variation = 0.1 * math.sin(latitude * 0.1) * math.cos(longitude * 0.1)
    eii = round(max(0.0, min(1.0, base_eii + variation)), 3)
    
    return {
        "geometry_type": "Point",
        "coordinates": {"latitude": latitude, "longitude": longitude},
        "values": {
            "eii": eii,
            "functional_integrity":    round(max(0.0, min(1.0, eii * 1.05 - 0.01)), 3),
            "structural_integrity":    round(max(0.0, min(1.0, eii * 0.92)), 3),
            "compositional_integrity": round(max(0.0, min(1.0, eii * 0.95)), 3),
        },
        "demo_mode": True,
        "note": "Demo data - set up Google Earth Engine for real data"
    }


# ── polygon / bbox helpers ────────────────────────────────────────────────────

def _bbox_to_polygon(bbox):
    minx, miny, maxx, maxy = bbox
    return {
        "type": "Polygon",
        "coordinates": [[
            [minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny],
        ]],
    }


def _parse_geometry(body):
    """Return a plain GeoJSON geometry dict from various input shapes."""
    if "bbox" in body:
        bbox = body["bbox"]
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            return _bbox_to_polygon(bbox)
        raise ValueError("bbox must be [minLon, minLat, maxLon, maxLat]")

    raw = body.get("geometry") or body
    if not isinstance(raw, dict):
        raise ValueError("Expected a GeoJSON geometry object, Feature, or bbox array")
    if raw.get("type") == "Feature":
        raw = raw["geometry"]
    if raw.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError(f"Geometry type must be Polygon or MultiPolygon, got '{raw.get('type')}'")
    return raw


def _geom_centroid(geom):
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    return sum(lons) / len(lons), sum(lats) / len(lats)


def get_region_stats_from_gee(geom: dict) -> dict:
    """Mean EEI values across a polygon/bbox region using reduceRegion."""
    if not initialize_ee():
        return {"error": "Google Earth Engine not initialized."}
    try:
        ee_geom = ee.Geometry(geom)
        image = ee.Image(EEI_ASSET_PATH)
        bands = ["eii", "functional_integrity", "structural_integrity", "compositional_integrity"]
        stats = image.select(bands).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=ee_geom,
            scale=300,
            maxPixels=1e9,
        )
        result = stats.getInfo()
        return {
            "geometry_type": geom["type"],
            "values": {k: (round(v, 4) if v is not None else None) for k, v in result.items()},
            "source": "Google Earth Engine - Landler Open Data",
        }
    except Exception as e:
        return {"error": f"GEE region query failed: {e}"}


def get_region_stats_demo(geom: dict) -> dict:
    """Latitude-based demo estimates for a region."""
    lon, lat = _geom_centroid(geom)
    abs_lat = abs(lat)

    if abs_lat < 23:
        base = 0.65
    elif abs_lat < 35:
        base = 0.45
    elif abs_lat < 55:
        base = 0.50
    elif abs_lat < 66:
        base = 0.60
    else:
        base = 0.55

    base += 0.1 * math.sin(lat * 0.1) * math.cos(lon * 0.1)
    eii = round(max(0.0, min(1.0, base)), 3)

    return {
        "geometry_type": geom["type"],
        "values": {
            "eii":                     eii,
            "functional_integrity":    round(max(0.0, min(1.0, eii * 1.05 - 0.01)), 3),
            "structural_integrity":    round(max(0.0, min(1.0, eii * 0.92)), 3),
            "compositional_integrity": round(max(0.0, min(1.0, eii * 0.95)), 3),
        },
        "demo_mode": True,
        "note": "Demo data - set up Google Earth Engine for real data",
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/eei-stats', methods=['POST'])
def eei_stats():
    try:
        data = request.get_json()
        latitude = float(data.get('latitude', 0))
        longitude = float(data.get('longitude', 0))
        
        # Validate coordinates
        if not (-90 <= latitude <= 90):
            return jsonify({"error": "Latitude must be between -90 and 90"}), 400
        if not (-180 <= longitude <= 180):
            return jsonify({"error": "Longitude must be between -180 and 180"}), 400
        
        # Check if we have credentials - try to initialize GEE if not done yet
        has_credentials = os.environ.get('GEE_PROJECT_ID') and (
            os.environ.get('GEE_SERVICE_ACCOUNT_KEY') or os.environ.get('GEE_SECRET_ID'))
        
        if has_credentials and not ee_initialized and not ee_init_attempted:
            initialize_ee()
        
        # Use real GEE data if initialized
        if ee_initialized:
            stats = get_eei_stats_from_gee(latitude, longitude)
            if "error" not in stats:
                return jsonify(stats)
            # Fall back to demo mode on error
            demo_stats = get_eei_stats_demo(latitude, longitude)
            demo_stats["gee_error"] = stats.get("error", "GEE unavailable")
            return jsonify(demo_stats)
        
        # Use demo mode if GEE not available
        stats = get_eei_stats_demo(latitude, longitude)
        if ee_init_error:
            stats["gee_error"] = ee_init_error
        return jsonify(stats)
    
    except (ValueError, TypeError) as e:
        return jsonify({"error": "Invalid coordinates provided"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/eei-batch', methods=['POST'])
def eei_batch():
    """Get EEI values for multiple coordinates (up to MAX_BATCH_COORDINATES)."""
    try:
        data = request.get_json()
        coordinates = data.get('coordinates', [])

        if not coordinates:
            return jsonify({"error": "No coordinates provided"}), 400

        # Elegant fallback: rather than rejecting an oversized batch with a
        # 400, process the first MAX_BATCH_COORDINATES points and flag the
        # truncation in the response so the caller can react if it cares.
        requested_count = len(coordinates)
        truncated = requested_count > MAX_BATCH_COORDINATES
        if truncated:
            coordinates = coordinates[:MAX_BATCH_COORDINATES]

        # Check if we have credentials
        has_credentials = os.environ.get('GEE_PROJECT_ID') and (
            os.environ.get('GEE_SERVICE_ACCOUNT_KEY') or os.environ.get('GEE_SECRET_ID'))
        
        if has_credentials and not ee_initialized and not ee_init_attempted:
            initialize_ee()
        
        results = []
        valid_values = {"eii": [], "functional_integrity": [], "structural_integrity": [], "compositional_integrity": []}
        
        for coord in coordinates:
            try:
                lat = float(coord.get('latitude', 0))
                lon = float(coord.get('longitude', 0))
                
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    results.append({
                        "coordinates": {"latitude": lat, "longitude": lon},
                        "error": "Invalid coordinates"
                    })
                    continue
                
                # Get EEI data
                if ee_initialized:
                    stats = get_eei_stats_from_gee(lat, lon)
                    if "error" in stats:
                        stats = get_eei_stats_demo(lat, lon)
                else:
                    stats = get_eei_stats_demo(lat, lon)
                
                results.append(stats)
                
                # Collect values for averaging
                values = stats.get("values", {})
                for key in valid_values.keys():
                    val = values.get(key)
                    if val is not None:
                        valid_values[key].append(val)
                        
            except (ValueError, TypeError):
                results.append({
                    "coordinates": coord,
                    "error": "Invalid coordinate format"
                })
        
        # Calculate averages
        averages = {}
        for key, vals in valid_values.items():
            if vals:
                averages[key] = round(sum(vals) / len(vals), 3)
            else:
                averages[key] = None
        
        return jsonify({
            "results": results,
            "averages": averages,
            "count": len(results),
            "valid_count": len(valid_values["eii"]),
            "requested_count": requested_count,
            "truncated": truncated,
            "max_batch": MAX_BATCH_COORDINATES,
            "demo_mode": not ee_initialized
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/query', methods=['POST'])
def query_region():
    """Mean EEI values for a GeoJSON polygon or bounding box."""
    try:
        body = request.get_json(force=True)
        if not body:
            return jsonify({"error": "Request body must be JSON"}), 400

        try:
            geom = _parse_geometry(body)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400

        has_credentials = os.environ.get('GEE_PROJECT_ID') and (
            os.environ.get('GEE_SERVICE_ACCOUNT_KEY') or os.environ.get('GEE_SECRET_ID'))
        if has_credentials and not ee_initialized and not ee_init_attempted:
            initialize_ee()

        if ee_initialized:
            result = get_region_stats_from_gee(geom)
            if "error" not in result:
                return jsonify(result)
            demo = get_region_stats_demo(geom)
            demo["warning"] = result["error"]
            return jsonify(demo)

        result = get_region_stats_demo(geom)
        if ee_init_error:
            result["gee_error"] = ee_init_error
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "ee_initialized": ee_initialized
    })



@app.route('/api')
def api_docs():
    """API documentation endpoint"""
    return jsonify({
        "name": "EEI Explorer API",
        "version": "1.1",
        "description": "Ecosystem Integrity Index lookup service powered by Google Earth Engine",
        "endpoints": {
            "POST /api/eei-stats": {
                "description": "Get EEI values for a single geographic point",
                "request_body": {
                    "latitude": "number (-90 to 90)",
                    "longitude": "number (-180 to 180)"
                },
                "response": {
                    "geometry_type": "Point",
                    "coordinates": {"latitude": "number", "longitude": "number"},
                    "values": {
                        "eii": "Overall Ecosystem Integrity Index (0-1)",
                        "functional_integrity": "Functional integrity score (0-1)",
                        "structural_integrity": "Structural integrity score (0-1)",
                        "compositional_integrity": "Compositional integrity score (0-1)"
                    },
                    "source": "Data source information"
                },
                "example_request": {
                    "latitude": -3.4653,
                    "longitude": -62.2159
                }
            },
            "POST /api/eei-batch": {
                "description": "Get EEI values for multiple coordinates (up to 100) with averages",
                "request_body": {
                    "coordinates": "[{latitude, longitude}, ...] (max 100; extra coordinates are dropped, not rejected)"
                },
                "response": {
                    "results": "Array of individual EEI results",
                    "averages": "Average values across all valid locations",
                    "count": "Total coordinates processed",
                    "valid_count": "Locations with valid EEI data",
                    "requested_count": "Coordinates sent in the request",
                    "truncated": "True if the request exceeded the 100-coordinate cap"
                },
                "example_request": {
                    "coordinates": [
                        {"latitude": -3.4653, "longitude": -62.2159},
                        {"latitude": 35.6762, "longitude": 139.6503}
                    ]
                }
            },
            "GET /api/health": {
                "description": "Check API health status"
            },
            "GET /api": {
                "description": "This documentation"
            },
            "POST /api/query": {
                "description": "Mean EEI values for a GeoJSON polygon or bounding box",
                "request_body": {
                    "geometry": "GeoJSON Polygon or Feature",
                    "bbox": "[minLon, minLat, maxLon, maxLat]"
                },
                "response": {
                    "geometry_type": "Polygon | MultiPolygon",
                    "values": {
                        "eii": "mean Overall EEI (0-1)",
                        "functional_integrity": "mean functional score (0-1)",
                        "structural_integrity": "mean structural score (0-1)",
                        "compositional_integrity": "mean compositional score (0-1)"
                    }
                },
                "example_request": {
                    "bbox": [-2.5, 51.3, -2.0, 51.6]
                }
            }
        },
        "data_source": "Landler EEI Global Dataset via Google Earth Engine"
    })


if __name__ == '__main__':
    # Don't initialize EE on startup - it will be initialized on demand
    # This prevents hanging if GEE auth is not configured
    print("Starting EEI Explorer Flask app...")
    print("Note: Google Earth Engine will be initialized on first API request")
    print("Demo mode will be used if GEE authentication is not configured")
    app.run(host='0.0.0.0', port=5000, debug=False)
