from itertools import product, cycle
import numpy as np
import geopandas as gp
from shapely.geometry import LineString, Point
from .base import pairwise, reduce_mem_usage

CRS = 'EPSG:32630'
def readupdate_crs(crs='EPSG:32630'):
    """
    Return CRS and/or set CRS value

    :param crs: geographic projection code
    """
    global CRS
    CRS = crs
    return CRS

def get_point(this_geoseries):
    """
    Return numpy coordinate pair array from GeoPandas Points geometry

    :param gs: GeoPanda dataseries
    """
    return np.array(this_geoseries['geometry'].xy).reshape(-1)

def get_points(gf):
    """
    Return numpy 2D coordinate array from GeoDataFrame Points geometry
    Also GeoSeries Points geometry with recursive call

    :param gf: GeoPanda dataframe or series
    """
    try:
        return np.array([gf['geometry'].x.values, gf['geometry'].y.values]).T
    except KeyError:
        return get_points(gf.rename('geometry').reset_index())

def get_boundary(gf, overlap=0.0):
    """
    Return rectangle array that covers area of GeoDataFrame extended by overlap

    :param gf: GeoDataFrame
    :param overlap: distance to extend coverage
    """
    offset = np.asarray([[-overlap, -overlap], [overlap, overlap]])
    try:
        r = gf.bounds
    except AttributeError:
        r = gf
    return np.asarray([r.min().values[:2], r.max().values[2:]]) + offset

def get_boundaries(gf, overlap=0.0):
    """
    Return rectangle array that covers area of GeoDataFrame extended by overlap

    :param gf: GeoDataFrame
    :param overlap: distance to extend coverage
    """
    offset = np.asarray([[-overlap, -overlap], [overlap, overlap]])
    r = gf.bounds
    return r.values.reshape(-1, 2, 2) + offset

def get_extent(u, d=100.0):
    """
    Return x, y integer units of distance 'd' that would covers the extent of
    GeoDataFrame, or its numpy extent array

    :param u: GeoDataFrame or numpy array
    :param d: distance parameter
    """
    try:
        r = np.array(u.bounds).reshape(-1, 2).T
    except AttributeError:
        try:
            return get_extent(u['geometry'], d)
        except TypeError:
            pass
        r = u.T
    return (np.ceil(np.diff(r) / d)).astype(int).reshape(-1)

def get_centres(gf):
    """
    Return GeoSeries of centres points for GeoDataFrame

    :param gf: GeoDataFrame
    """
    v = np.array(gf.bounds)[:, [0, 2, 1, 3]]
    r = v.reshape(-1, 2).sum(axis=1).reshape(-1, 2) / 2.0
    return gp.points_from_xy(*r.T)

def get_mesharray(xy_array, centre, d):
    """
    Return 2D xr by yr numpy square-mesh array of points covering GeoDataFrame.
    Centred on the point 'centre' and separated at a distance 'd'

    :param xy_array: size of m, n
    :param centre: GeoDataFrame centre-point
    :param d: square edge size
    """
    xoffset, yoffset = centre - (xy_array * d / 2.0)
    m, n = xy_array
    x_linear = np.linspace(xoffset, xoffset + m * d, m)
    y_linear = np.linspace(yoffset, yoffset + n * d, n)
    x_s, y_s = np.meshgrid(x_linear, y_linear, sparse=True)
    r = list(product(x_s.reshape(-1), y_s.reshape(-1)))
    return np.array(r).reshape(-1, 2)

def get_meshframe(gf, centre, d, crs=CRS):
    """
    Return GeoDataFrame of squares that cover GeoDataFrame 'gf'

    :param gf: GeoDataFrame to be
    :param centre: GeoDataFrame centre-point
    :param d: square edge size
    :param crs: geographic projection code
    """
    extent = get_extent(gf, d)
    mesh = get_mesharray(extent, centre, d)
    r = gp.GeoDataFrame(geometry=gp.points_from_xy(*mesh.T)).set_crs(crs)
    r = gp.clip(r, gf['geometry'])
    r = r.loc[r.index]
    return r.reset_index(drop=True)

def get_meshpoints(gf, d, crs=CRS):
    """
    Return GeoDataFrame of square center-points that cover GeoDataFrame 'gf'
    :param gf: GeoDataFrame to be covered in squares
    :param centre: GeoDataFrame centre point
    :param d: square side length
    :param crs: coordinate reference projection geometry string
    """

    boundary = get_boundary(gf, d)
    extent = get_extent(boundary, d)
    centre = boundary.T.sum(axis=1) / 2.0
    n, m = extent
    mesh = product(range(n), range(m))
    points = (Point(centre + d * (np.asarray(p) - extent / 2.0)) for p in mesh)
    return gp.GeoDataFrame(geometry=list(points)).set_crs(crs)

def get_squares(points, d, boost=0.0):
    """
    Return 2D numpy point square mesh array.
    Each square centred on the point in 'points' and length 'd'
    A 'boost' can be applied to ensure overlap due to rounding errors

    :param points: 2D numpy array of square centre points
    :param d: square-side length
    :param boost: square-side overlap
    """
    d = d + boost
    return np.hstack([points - d,
                      points - np.array([d, -d]),
                      points + d,
                      points + np.array([d, -d])]).reshape(-1, 4, 2)


def get_pairs(triangles):
    """
    Return list of start and end point pairs for array of triangle simplices
    For example, triangles [['A', 'B', 'C'], ['B', 'C', 'D']] gives
    [('A', 'B'), ('B', 'C'), ('C', 'A'), ('B', 'C'), ('C', 'D'), ('D', 'B')]

    :param triangles: list of triangles
    """
    r = []
    for i in triangles:
        j = pairwise(cycle(i))
        for _ in range(3):
            r.append(next(j))
    return r

def get_lines(triangles, data, points, crs=CRS):
    """
    Return a GeoDataFrame deduplicated lines from an array of triangles

    :param triangles: list of triangle simplices
    :param data: data column values for lines
    :param points: numpy array of triangle point coordinates
    :param crs: geographic projection code
    """
    s = np.array(list({tuple(sorted(i)) for i in get_pairs(triangles)}))
    this_geometry = [LineString(i) for i in points[s]]
    r = gp.GeoDataFrame(columns=['from', 'to'], data=data[s], geometry=this_geometry)
    r.index = ['L{(str(i+1).zfill(5))}' for i in r.index]
    return r.set_crs(crs)

def gf_reduce_mem_usage(gf, output=True, drop=True):
    """ iterate through all the columns of a GeoDataFrame, drop non-numerical
        data and modify the data type to reduce memory usag
        https://www.kaggle.com/gemartin/load-data-reduce-memory-usage
    """
    if output:
        start_mem = gf.memory_usage(deep=True).sum() / 1024**2
        print(f'Memory usage of dataframe is {round(start_mem, 2)} MB')
    this_geometry = gf['geometry']
    gf = gf.drop(columns='geometry')
    gf = reduce_mem_usage(gf, output=False, drop=drop)
    gf['geometry'] = this_geometry
    if output:
        end_mem = gf.memory_usage(deep=True).sum() / 1024**2
        print(f'Memory usage after optimization is: {round(end_mem, 2)} MB')
        print(f'Decreased by {round((100 * (start_mem - end_mem) / start_mem), 2)}%'.format)
    return gf
