import geopandas as gpd
import pandas as pd
import yaml


def rank_known_points(stands: gpd.GeoDataFrame, known_points: list[dict]) -> pd.DataFrame:
    pts = gpd.GeoDataFrame(
        known_points,
        geometry=gpd.points_from_xy([p["lon"] for p in known_points], [p["lat"] for p in known_points]),
        crs="EPSG:4326",
    ).to_crs(stands.crs)

    joined = gpd.sjoin_nearest(pts, stands[["stand_id", "R", "geometry"]], how="left")

    r_values = stands["R"].to_numpy()
    joined["rank_pct"] = joined["R"].apply(lambda r: float((r_values < r).mean() * 100.0))

    return joined[["name", "label", "stand_id", "R", "rank_pct"]].reset_index(drop=True)


def load_known_points(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
