from shapely.geometry import box
import geopandas as gpd


def search_gdf_bounds(gdf, tile_bounds):
    """Use `tile_bounds` to subset `gdf` and return the intersect.

    Arguments
    ---------
    gdf : :py:class:`geopandas.GeoDataFrame`
        A :py:class:`geopandas.GeoDataFrame` of polygons to subset.
    tile_bounds : tuple
        A tuple of shape ``(W, S, E, N)`` that denotes the boundaries of a
        tile.

    Returns
    -------
    smallGdf : :py:class:`geopandas.GeoDataFrame`
        The subset of `gdf` that overlaps with `tile_bounds` .

    """

    tile_polygon = box(tile_bounds)
    smallGdf = search_gdf_polygon(gdf, tile_polygon)

    return smallGdf


def search_gdf_polygon(gdf, tile_polygon):
    """Find polygons in a GeoDataFrame that overlap with `tile_polygon` .

    Arguments
    ---------
    gdf : :py:class:`geopandas.GeoDataFrame`
        A :py:class:`geopandas.GeoDataFrame` of polygons to search.
    tile_polygon : :py:class:`shapely.geometry.Polygon`
        A :py:class:`shapely.geometry.Polygon` denoting a tile's bounds.

    Returns
    -------
    precise_matches : :py:class:`geopandas.GeoDataFrame`
        The subset of `gdf` that overlaps with `tile_polygon` . If
        there are no overlaps, this will return an empty
        :py:class:`geopandas.GeoDataFrame`.

    """

    sindex = gdf.sindex
    possible_matches_index = list(sindex.intersection(tile_polygon.bounds))
    possible_matches = gdf.iloc[possible_matches_index]
    precise_matches = possible_matches[
        possible_matches.intersects(tile_polygon)
        ]
    if precise_matches.empty:
        precise_matches = gpd.GeoDataFrame(geometry=[])
    return precise_matches


def vector_tile_utm(gdf, tile_bounds, min_partial_perc=0.1,
                    geom_type="Polygon", use_sindex=True):
    """Wrapper for :func:`clip_gdf` that clips `tile_bounds` to a polygon.

    Arguments
    ---------
    gdf : :class:`geopandas.GeoDataFrame`
        A :py:class:`geopandas.GeoDataFrame` of polygons to clip.
    tile_bounds : list-like of floats
        :obj:`list` of shape ``(W, S, E, N)`` denoting the boundaries of an
        imagery tile. Converted to a polygon for :func:`clip_gdf`.
    min_partial_perc : float
        The minimum fraction of an object in `gdf` that must be
        preserved. Defaults to 0.0 (include any object if any part remains
        following clipping).
    use_sindex : bool, optional
        Use the `gdf` sindex be used for searching. Improves efficiency
        but requires `libspatialindex <http://libspatialindex.github.io/>`__ .

    Returns
    -------
    small_gdf : :py:class:`geopandas.GeoDataFrame`
        `gdf` with all contained objects clipped to `tile_bounds`.
        See notes above for details on additional clipping columns added.
    """
    tile_polygon = box(*tile_bounds)
    small_gdf = clip_gdf(gdf, tile_polygon,
                         min_partial_perc=min_partial_perc,
                         geom_type=geom_type
                         )

    return small_gdf


def clip_gdf(gdf, poly_to_cut, min_partial_perc=0.0, geom_type="Polygon",
             use_sindex=True):
    """Clip GDF to a provided polygon.

    Clips objects within `gdf` to the region defined by
    `poly_to_cut`. Also adds several columns to the output::

        `origarea`
            The original area of the polygons (only used if `geom_type` ==
            ``"Polygon"``).
        `origlen`
            The original length of the objects (only used if `geom_type` ==
            ``"LineString"``).
        `partialDec`
            The fraction of the object that remains after clipping
            (fraction of area for Polygons, fraction of length for
            LineStrings.) Can filter based on this by using `min_partial_perc`.
        `truncated`
            Boolean indicator of whether or not an object was clipped.

    Arguments
    ---------
    gdf : :py:class:`geopandas.GeoDataFrame`
        A :py:class:`geopandas.GeoDataFrame` of polygons to clip.
    poly_to_cut : :py:class:`shapely.geometry.Polygon`
        The polygon to clip objects in `gdf` to.
    min_partial_perc : float, optional
        The minimum fraction of an object in `gdf` that must be
        preserved. Defaults to 0.0 (include any object if any part remains
        following clipping).
    geom_type : str, optional
        Type of objects in `gdf`. Can be one of
        ``["Polygon", "LineString"]`` . Defaults to ``"Polygon"`` .
    use_sindex : bool, optional
        Use the `gdf` sindex be used for searching. Improves efficiency
        but requires `libspatialindex <http://libspatialindex.github.io/>`__ .

    Returns
    -------
    cutGeoDF : :py:class:`geopandas.GeoDataFrame`
        `gdf` with all contained objects clipped to `poly_to_cut` .
        See notes above for details on additional clipping columns added.

    """

    # check if geoDF has origAreaField

    if use_sindex:
        gdf = search_gdf_polygon(gdf, poly_to_cut)

    # if geom_type == "LineString":
    if 'origarea' in gdf.columns:
        pass
    else:
        if "geom_type" == "LineString":
            gdf['origarea'] = 0
        else:
            gdf['origarea'] = gdf.area
    if 'origlen' in gdf.columns:
        pass
    else:
        if "geom_type" == "LineString":
            gdf['origlen'] = gdf.length
        else:
            gdf['origlen'] = 0
    # TODO must implement different case for lines and for spatialIndex
    # (Assume RTree is already performed)

    cutGeoDF = gdf.copy()
    cutGeoDF.geometry = gdf.intersection(poly_to_cut)

    if geom_type == 'Polygon':
        cutGeoDF['partialDec'] = cutGeoDF.area / cutGeoDF['origarea']
        cutGeoDF = cutGeoDF.loc[cutGeoDF['partialDec'] > min_partial_perc, :]
        cutGeoDF['truncated'] = (cutGeoDF['partialDec'] != 1.0).astype(int)
    else:
        cutGeoDF = cutGeoDF[cutGeoDF.geom_type != "GeometryCollection"]
        cutGeoDF['partialDec'] = 1
        cutGeoDF['truncated'] = 0
    # TODO: IMPLEMENT TRUNCATION MEASUREMENT FOR LINESTRINGS

    return cutGeoDF