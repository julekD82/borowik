import geopandas as gpd


def _compartment_key(adr_for: str) -> str:
    """A stand's adr_for ("RDLP-Nadl-Obreb-Oddzial(2 tokens)-Poddzial-Nr",
    e.g. "02-10-1-01-126   -d   -97") and its containing G_COMPARTMENT's own
    adr_for ("02-10-1-01-126   -    -", pododdzial/suffix blank) share the
    same first 5 dash-separated tokens byte-for-byte (verified on the real
    Kedzierzyn package: 3301/3301 D-STAN stands matched a compartment this
    way) -- far cheaper and more reliable than a spatial join."""
    return "-".join(adr_for.split("-")[:5])


def compartment_boundary_features(
    stands: gpd.GeoDataFrame, compartments: gpd.GeoDataFrame,
) -> dict[str, tuple[float | None, float | None]]:
    """Plan 1.6.4: for every stand, its distance to the nearest boundary of
    the G_COMPARTMENT ("oddzial") it belongs to, and how much of the
    stand's own perimeter actually lies on that compartment boundary --
    Faza 6 hypothesis (linie oddzialowe/dukty as light/soil-disturbance
    edges), diagnostics-only, never touches H/R.

    `stands`/`compartments` need `adr_for` + `geometry` columns (same CRS,
    projected -- distances/lengths are in that CRS's units). A stand whose
    key matches no compartment (or an empty `compartments`) gets
    `(None, None)` rather than raising -- same "missing package data never
    breaks the run" spirit as pipeline.bdl_packages."""
    comp_by_key = {}
    for adr_for, geom in zip(compartments["adr_for"], compartments.geometry):
        comp_by_key[_compartment_key(adr_for)] = geom

    result: dict[str, tuple[float | None, float | None]] = {}
    for adr_for, geom in zip(stands["adr_for"], stands.geometry):
        comp_geom = comp_by_key.get(_compartment_key(adr_for))
        if comp_geom is None:
            result[adr_for] = (None, None)
            continue
        boundary = comp_geom.boundary
        dist = float(geom.centroid.distance(boundary))
        shared_len = float(geom.boundary.intersection(boundary).length)
        result[adr_for] = (dist, shared_len)
    return result
