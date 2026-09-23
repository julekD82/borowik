import io

import geopandas as gpd
import pandas as pd
import requests

from pipeline.tiles import wfs_bbox_param

DEFAULT_GDOS_WFS_URL = "https://sdi.gdos.gov.pl/wfs"
DEFAULT_GDOS_LAYERS = ("GDOS:Rezerwaty", "GDOS:ParkiNarodowe")


def _fetch_gdos_layer(layer: str, bbox: tuple, base_url: str) -> gpd.GeoDataFrame:
    """A single, unpaginated WFS 2.0.0 GetFeature call. Unlike
    pipeline.bdl.fetch_bdl (which this module originally reused, see Task 4's
    ledger ruling), this never sends startIndex/count: verified live
    2026-09-24, GDOS:Rezerwaty has no natural sort key, so GeoServer rejects
    ANY GetFeature request carrying startIndex -- even startIndex=0 -- with
    "Cannot do natural order without a primary key". A single 10x10 km tile
    never holds more than a handful of reserves/parks, so skipping
    pagination is a safe, deliberate simplification for this data source
    only (BDL's own layers keep using fetch_bdl's paginated client)."""
    resp = requests.get(base_url, params={
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": layer, "outputFormat": "application/json",
        "bbox": wfs_bbox_param(bbox),
    }, timeout=30)
    resp.raise_for_status()
    return gpd.read_file(io.BytesIO(resp.content))


def fetch_protected_areas(bbox: tuple, layers: tuple = DEFAULT_GDOS_LAYERS,
                            base_url: str = DEFAULT_GDOS_WFS_URL) -> gpd.GeoDataFrame:
    frames = [_fetch_gdos_layer(layer, bbox, base_url) for layer in layers]
    frames = [f for f in frames if len(f)]
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:2180")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)


def mark_gdos_blocked(stands: gpd.GeoDataFrame, protected_areas: gpd.GeoDataFrame) -> pd.Series:
    """True where a stand's polygon intersects any GDOŚ reserve/national-park
    polygon. Cheap all-False short-circuit for the overwhelmingly common case
    of a tile with no protected areas at all."""
    if len(protected_areas) == 0:
        return pd.Series(False, index=stands.index)
    hits = gpd.sjoin(stands[["geometry"]], protected_areas[["geometry"]],
                       how="left", predicate="intersects")
    blocked = hits.groupby(level=0)["index_right"].apply(lambda s: s.notna().any())
    return blocked.reindex(stands.index, fill_value=False)
