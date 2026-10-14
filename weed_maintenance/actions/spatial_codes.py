"""Spatial region and district assignment for weed locations."""

import time
from contextlib import contextmanager

import geopandas as gpd
import pandas as pd

# Reason: one response for every district polygon is large enough that ArcGIS
# intermittently returns Content-Encoding: gzip with a body zlib cannot decode.
BOUNDARY_PAGE_SIZE = 8
BOUNDARY_ATTEMPTS = 5

def arcgis_to_geopandas(feature_set, geometry_col='SHAPE'):
    """Convert ArcGIS FeatureSet to GeoPandas DataFrame with geometry validation"""
    from shapely.geometry import Point, Polygon, LineString
    from shapely.validation import make_valid
    
    # Extract features and geometries
    features = []
    geometries = []
    
    for feature in feature_set.features:
        # Get attributes
        attrs = feature.attributes.copy()
        features.append(attrs)
        
        # Convert geometry
        geom_dict = feature.geometry
        if geom_dict:
            try:
                # Handle different ArcGIS geometry types
                if 'x' in geom_dict and 'y' in geom_dict:
                    # Point geometry
                    geom = Point(geom_dict['x'], geom_dict['y'])
                elif 'rings' in geom_dict:
                    # Polygon geometry
                    rings = geom_dict['rings']
                    if rings and len(rings) > 0:
                        # Create polygon from rings (exterior ring first, then holes)
                        exterior = rings[0]
                        holes = rings[1:] if len(rings) > 1 else None
                        geom = Polygon(exterior, holes)
                        
                        # Fix invalid geometries
                        if not geom.is_valid:
                            geom = make_valid(geom)
                    else:
                        geom = None
                elif 'paths' in geom_dict:
                    # Polyline geometry
                    paths = geom_dict['paths']
                    if paths and len(paths) > 0:
                        # Use first path for simplicity
                        geom = LineString(paths[0])
                    else:
                        geom = None
                else:
                    # Unknown geometry type
                    print(f"Warning: Unknown geometry type: {geom_dict}")
                    geom = None
                    
                geometries.append(geom)
            except Exception as e:
                print(f"Warning: Error converting geometry: {e}")
                geometries.append(None)
        else:
            geometries.append(None)
    
    # Create GeoDataFrame
    df = pd.DataFrame(features)
    gdf = gpd.GeoDataFrame(df, geometry=geometries)
    
    # Set CRS if available
    if feature_set.spatial_reference:
        wkid = feature_set.spatial_reference.get('wkid') or feature_set.spatial_reference.get('latestWkid')
        if wkid:
            try:
                gdf.crs = f"EPSG:{wkid}"
            except Exception:
                print(f"Warning: Could not set CRS for EPSG:{wkid}")
    
    return gdf

class _BoundaryFeatures:
    def __init__(self, features, spatial_reference):
        self.features = features
        self.spatial_reference = spatial_reference


def _request_headers(layer):
    connection = getattr(layer, "_con", None)
    session = getattr(connection, "_session", None)
    return getattr(session, "headers", None)


@contextmanager
def _uncompressed(layer):
    """Ask this layer's HTTP session not to gzip the response."""
    headers = _request_headers(layer)
    if headers is None:
        yield
        return
    previous = headers.get("Accept-Encoding")
    headers["Accept-Encoding"] = "identity"
    try:
        yield
    finally:
        if previous is None:
            headers.pop("Accept-Encoding", None)
        else:
            headers["Accept-Encoding"] = previous


def _object_ids(layer, sleep):
    result = None
    for attempt in range(1, BOUNDARY_ATTEMPTS + 1):
        try:
            result = layer.query(where="1=1", return_ids_only=True, return_geometry=False)
            break
        except OSError as error:
            if attempt == BOUNDARY_ATTEMPTS:
                raise
            print(f"    Boundary id query failed (attempt {attempt}/{BOUNDARY_ATTEMPTS}): {type(error).__name__}")
            sleep(attempt * 2)
    if isinstance(result, dict):
        field = result.get("objectIdFieldName") or "OBJECTID"
        return field, list(result.get("objectIds") or [])
    field = getattr(result, "objectIdFieldName", None) or "OBJECTID"
    return field, list(getattr(result, "objectIds", None) or [])


def _query_page(layer, remaining, out_fields, order_field, page_size, sleep):
    """Fetch one page, halving it when the response cannot be decoded."""
    size = page_size
    while True:
        batch = remaining[:size]
        try:
            result = layer.query(
                object_ids=batch,
                out_fields=out_fields,
                return_geometry=True,
                order_by_fields=order_field,
            )
            if isinstance(result, dict) or not hasattr(result, "features"):
                raise OSError("boundary query returned a raw response")
            if len(result.features) < len(batch):
                if len(batch) == 1:
                    print("    Boundary feature missing from response, continuing")
                    return result, 1, 1
                raise OSError(f"short boundary page {len(result.features)}/{len(batch)}")
            next_size = size if len(batch) == size else page_size
            return result, len(batch), next_size
        except OSError as error:
            if len(batch) == 1:
                print(f"    Boundary feature failed (attempt 1/{BOUNDARY_ATTEMPTS}): {type(error).__name__}")
                return _retry_one(layer, batch, out_fields, order_field, sleep)
            size = max(1, len(batch) // 2)
            print(f"    Boundary page failed ({type(error).__name__}), retrying {size} features")
            sleep(2)


def _retry_one(layer, batch, out_fields, order_field, sleep):
    for attempt in range(2, BOUNDARY_ATTEMPTS + 1):
        try:
            result = layer.query(
                object_ids=batch,
                out_fields=out_fields,
                return_geometry=True,
                order_by_fields=order_field,
            )
            if isinstance(result, dict) or not hasattr(result, "features"):
                raise OSError("boundary query returned a raw response")
            if not result.features:
                print("    Boundary feature missing from response, continuing")
            return result, 1, 1
        except OSError as error:
            if attempt == BOUNDARY_ATTEMPTS:
                raise
            print(f"    Boundary feature failed (attempt {attempt}/{BOUNDARY_ATTEMPTS}): {type(error).__name__}")
            sleep(attempt * 2)
    raise OSError("boundary feature failed")


def query_boundary_features(layer, out_fields, page_size=BOUNDARY_PAGE_SIZE, sleep=time.sleep):
    """Load a boundary layer in small geometry pages."""
    with _uncompressed(layer):
        order_field, object_ids = _object_ids(layer, sleep)
        features = []
        spatial_reference = None
        index = 0
        size = page_size
        while index < len(object_ids):
            page, taken, size = _query_page(
                layer, object_ids[index:], out_fields, order_field, size, sleep
            )
            features.extend(page.features)
            if spatial_reference is None:
                spatial_reference = getattr(page, "spatial_reference", None)
            index += taken
        return _BoundaryFeatures(features, spatial_reference)


def load_boundaries_as_geopandas(region_layer, district_layer):
    """Load boundary layers as GeoPandas DataFrames - SUPER FAST!"""
    print("Loading boundary layers with GeoPandas...")

    print("  Loading regions...")
    regions_gdf = arcgis_to_geopandas(query_boundary_features(region_layer, ["REGC_code"]))
    print(f"  Loaded {len(regions_gdf)} region boundaries")

    print("  Loading districts...")
    districts_gdf = arcgis_to_geopandas(query_boundary_features(district_layer, ["TALB_code"]))
    print(f"  Loaded {len(districts_gdf)} district boundaries")

    return regions_gdf, districts_gdf

def find_nearest_boundary(point_gdf, boundary_gdf, code_field, max_distance_m=1000):
    """Find nearest boundary for unassigned points within max_distance"""
    import numpy as np
    
    if len(point_gdf) == 0 or len(boundary_gdf) == 0:
        return point_gdf
    
    print(f"    → Searching for nearest boundaries within {max_distance_m}m...")
    
    # Calculate distance from each point to each boundary
    point_gdf = point_gdf.copy()
    nearest_codes = []
    nearest_distances = []
    
    for idx, point_row in point_gdf.iterrows():
        point_geom = point_row.geometry
        
        # Calculate distances to all boundaries
        distances = boundary_gdf.geometry.distance(point_geom)
        min_distance_idx = distances.idxmin()
        min_distance = distances.loc[min_distance_idx]
        
        if min_distance <= max_distance_m:
            nearest_code = boundary_gdf.loc[min_distance_idx, code_field]
            nearest_codes.append(nearest_code)
            nearest_distances.append(min_distance)
        else:
            nearest_codes.append(None)
            nearest_distances.append(min_distance)
    
    # Add results to dataframe
    point_gdf['nearest_code'] = nearest_codes
    point_gdf['nearest_distance'] = nearest_distances
    
    assigned_count = sum(1 for code in nearest_codes if code is not None)
    if assigned_count > 0:
        print(f"    → {assigned_count} points assigned to nearest boundaries (within {max_distance_m}m)")
    
    return point_gdf

def spatial_join_bulk(weeds_gdf, regions_gdf, districts_gdf):
    """Perform bulk spatial joins using GeoPandas with nearest boundary fallback - VERY FAST!"""
    print("Performing bulk spatial joins with GeoPandas...")
    
    # Ensure CRS match for spatial operations (use NZTM as target)
    target_crs = "EPSG:2193"  # New Zealand Transverse Mercator
    print(f"  Converting all layers to {target_crs}...")
    
    if weeds_gdf.crs != target_crs:
        weeds_gdf = weeds_gdf.to_crs(target_crs)
    if regions_gdf.crs != target_crs:
        regions_gdf = regions_gdf.to_crs(target_crs) 
    if districts_gdf.crs != target_crs:
        districts_gdf = districts_gdf.to_crs(target_crs)
        
    # Ensure all geometries are valid after CRS transformation
    print("  Validating and fixing geometries...")
    from shapely.validation import make_valid
    regions_gdf = regions_gdf.copy()
    districts_gdf = districts_gdf.copy()
    regions_gdf.geometry = regions_gdf.geometry.apply(lambda geom: geom if geom.is_valid else make_valid(geom))
    districts_gdf.geometry = districts_gdf.geometry.apply(lambda geom: geom if geom.is_valid else make_valid(geom))
    
    # Spatial join with regions
    print("  Joining with regions...")
    weeds_with_regions = gpd.sjoin(weeds_gdf, regions_gdf[['REGC_code', 'geometry']], 
                                   how='left', predicate='intersects')
    
    # Find unassigned regions and try nearest boundary assignment
    unassigned_regions = weeds_with_regions[weeds_with_regions['REGC_code'].isna()]
    if len(unassigned_regions) > 0:
        print(f"  → {len(unassigned_regions)} points lie outside region boundaries")
        nearest_regions = find_nearest_boundary(unassigned_regions, regions_gdf, 'REGC_code', max_distance_m=2000)
        
        # Update the main dataframe with nearest assignments
        assigned_count = 0
        for idx, row in nearest_regions.iterrows():
            if row['nearest_code'] is not None:
                weeds_with_regions.loc[idx, 'REGC_code'] = row['nearest_code']
                assigned_count += 1
        
        remaining_unassigned = len(unassigned_regions) - assigned_count
        if remaining_unassigned > 0:
            print(f"  → {remaining_unassigned} points remain unassigned (>2km from any region boundary)")
    
    # Spatial join with districts  
    print("  Joining with districts...")
    # Drop index columns that might conflict from previous join
    if 'index_right' in weeds_with_regions.columns:
        weeds_with_regions = weeds_with_regions.drop(columns=['index_right'])
    
    weeds_with_all = gpd.sjoin(weeds_with_regions, districts_gdf[['TALB_code', 'geometry']], 
                               how='left', predicate='intersects')
    
    # Find unassigned districts and try nearest boundary assignment
    unassigned_districts = weeds_with_all[weeds_with_all['TALB_code'].isna()]
    if len(unassigned_districts) > 0:
        print(f"  → {len(unassigned_districts)} points lie outside district boundaries")
        nearest_districts = find_nearest_boundary(unassigned_districts, districts_gdf, 'TALB_code', max_distance_m=2000)
        
        # Update the main dataframe with nearest assignments
        assigned_count = 0
        for idx, row in nearest_districts.iterrows():
            if row['nearest_code'] is not None:
                weeds_with_all.loc[idx, 'TALB_code'] = row['nearest_code']
                assigned_count += 1
        
        remaining_unassigned = len(unassigned_districts) - assigned_count
        if remaining_unassigned > 0:
            print(f"  → {remaining_unassigned} points remain unassigned (>2km from any district boundary)")
    
    # Clean up the results
    weeds_with_all['RegionCode_new'] = weeds_with_all['REGC_code']
    weeds_with_all['DistrictCode_new'] = weeds_with_all['TALB_code']
    
    # Calculate and display assignment success rate
    total_points = len(weeds_with_all)
    region_assigned = weeds_with_all['RegionCode_new'].notna().sum()
    district_assigned = weeds_with_all['DistrictCode_new'].notna().sum()
    
    print("\n✅ Spatial assignment complete:")
    print(f"   Region assignment: {region_assigned:,}/{total_points:,} points ({region_assigned/total_points*100:.2f}%)")
    print(f"   District assignment: {district_assigned:,}/{total_points:,} points ({district_assigned/total_points*100:.2f}%)")
    
    # Keep only necessary columns
    result_cols = ['OBJECTID', 'RegionCode', 'DistrictCode', 'RegionCode_new', 'DistrictCode_new']
    result_cols = [col for col in result_cols if col in weeds_with_all.columns]
    
    return weeds_with_all[result_cols]

def plan_spatial_updates(feature_set, region_layer, district_layer):
    """Region and district changes for the features already loaded by the pipeline."""
    if not feature_set.features:
        return {}

    print("Converting to GeoPandas...")
    weeds_gdf = arcgis_to_geopandas(feature_set)
    regions_gdf, districts_gdf = load_boundaries_as_geopandas(region_layer, district_layer)
    results_df = spatial_join_bulk(weeds_gdf, regions_gdf, districts_gdf)

    print("Identifying features needing spatial updates...")
    updates = {}
    for _, row in results_df.iterrows():
        attributes = {}
        if pd.notna(row.get("RegionCode_new")) and row.get("RegionCode_new") != row.get("RegionCode"):
            attributes["RegionCode"] = row["RegionCode_new"]
        if pd.notna(row.get("DistrictCode_new")) and row.get("DistrictCode_new") != row.get("DistrictCode"):
            attributes["DistrictCode"] = row["DistrictCode_new"]
        if attributes:
            updates[int(row["OBJECTID"])] = attributes
    return updates
