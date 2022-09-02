"""
Module with population statistic functions
"""

import geopandas as gp
from scipy.spatial import cKDTree
from shapely.geometry import Polygon
from .geometry import CRS, get_points, get_squares

def get_density(df):
    """
    Return population per m^2 density from pandas dataframe.

    :param df: dataframe with 'population' and 'area' columns
    """
    return (1.0E6 * df['population'] / df['area'] ).round(1)

def get_heatframe(points, this_frame, key, n_count=15, crs=CRS):
    """
    Return GeoDataFrame 

    :param points:
    :param this_frame:
    :param key:
    :param n_count:
    :param crs:
    """
    tree = cKDTree(get_points(this_frame))
    grid = get_points(points)
    d, i = tree.query(grid, n_count)
    if (d == 0.0).any():
        d = d.T[1:].T
        i = i.T[1:].T

    weight = this_frame[key]
    u = 1.0E3 / d.sum(1)
    v = (1.0 * weight.values[i] / d).sum(1)
    w = (1.0 * weight.values[i] * weight.values[i] / d).sum(1)
    return gp.GeoDataFrame(data={'distance': u, 'weight': v, 'weight2': w},
                           geometry=points['geometry']).set_crs(crs)

def get_heatmap(mesh, geography, i_class, d, connections=512, key='population', crs=CRS):
    """
    Return GeoDataFrame 

    :param mesh:
    :param geography:
    :param i_class:
    :param d:
    :param key:
    :param connections:
    :param crs:
    """
    heatmap = get_heatframe(mesh, geography, key, connections)
    heatmap['class'] = i_class
    squares = get_squares(get_points(heatmap), d / 2.0, 0.2)
    heatmap['geometry'] = [Polygon(v) for v in squares]
    return heatmap.set_crs(crs)
