#!/usr/bin/env python3

import os
import datetime as dt
from itertools import cycle, tee

import numpy as np

import pandas as pd
import geopandas as gp
from shapely.geometry import Polygon

from scipy.spatial import cKDTree
from scipy.spatial import Delaunay

from herbert.base import archive
import herbert.geometry as hg

pd.set_option('display.max_columns', None)

CRS = hg.readupdate_crs('EPSG:32630')

START = dt.datetime.now()

print('Load_boundaries')
FILEPATH = 'bkm64.gpkg'

try:
    BOUNDARIES
except NameError:
    BOUNDARIES = gp.read_file(FILEPATH, layer='fit p2 boundary').to_crs(CRS)

print(dt.datetime.now() - START)
print('Write boundaries centres and boxes')
KEYS = ['class', 'area', 'population']
CENTRES = gp.GeoDataFrame(data=BOUNDARIES[KEYS],
                          geometry=hg.get_centres(BOUNDARIES)).set_crs(CRS)
BOXES = gp.GeoDataFrame(data=BOUNDARIES[KEYS],
                        geometry=BOUNDARIES.envelope).set_crs(CRS)

print(dt.datetime.now() - START)
LAYER = 'OA'
print(f'Read geography {LAYER}')

try:
    GEOGRAPHY
except NameError:
    GEOGRAPHY = gp.read_file('geography.gpkg', layer=LAYER).to_crs(CRS)
    GEOGRAPHY['geometry'] = GEOGRAPHY.centroid

FILEPATH = 'output/heatmap.gpkg'
archive(FILEPATH)
CENTRES.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='centres')
BOXES.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='boundaries')

D = 4096.0

FILESTUB = os.path.basename(FILEPATH).split('.')[0]
FILEDIR = os.path.dirname(FILEPATH)

def get_heatmap(points, gf, k, n=15):
    tree = cKDTree(hg.get_points(gf))
    grid = hg.get_points(points)
    d, i = tree.query(grid, n)

    weights = gf[k]
    u = 1.0E3 / d.sum(1)
    v = (1.0 * weights.values[i] / d).sum(1)
    w = (1.0 * weights.values[i] * weights.values[i] / d).sum(1)
    return gp.GeoDataFrame(data={'distance': u, 'weight': v, 'weight2': w},
                           geometry=points['geometry']).set_crs(CRS)

TOWNS = gp.GeoDataFrame(columns=['name', 'class', 'area',
                                 'population', 'geometry'], dtype=int)

D = 2048
N = 512

for C, BOUNDARY in BOUNDARIES.iterrows():
    print(dt.datetime.now() - START)
    CENTRE = hg.get_point(CENTRES.loc[C])

    XR, YR = hg.get_extent(BOUNDARY, D)
    print(f'Create {C + 1} of {BOUNDARIES.shape[0]}: {XR} x {YR} grid {D}m')

    MESH = hg.get_meshframe(BOUNDARY, CENTRE, D)
    print(dt.datetime.now() - START)
    print(f'Create heatmap {N} connections')
    HEATMAP = get_heatmap(MESH, GEOGRAPHY, 'population', N)
    HEATMAP['class'] = C

    idx1 = gp.clip(GEOGRAPHY['geometry'], BOUNDARY['geometry']).index
    FIELDS = ['area', 'population']
    TOWNS.loc[C, FIELDS] = GEOGRAPHY.loc[idx1, FIELDS].sum()
    TOWNS.loc[C, 'name'] = f'C{str(C).zfill(2)}'

    idx2 = HEATMAP['weight2'].idxmax()
    FIELDS = ['class', 'geometry']
    TOWNS.loc[C, FIELDS] = HEATMAP.loc[idx2, FIELDS]
    squares = hg.get_squares(hg.get_points(HEATMAP), D / 2.0)
    HEATMAP['geometry'] = [Polygon(v) for v in squares]

    print(dt.datetime.now() - START)
    print('Write heatmap')
    FILEPATHB = f'{FILEDIR}/{FILESTUB}-{str(C+1).zfill(2)}.gpkg'
    archive(FILEPATHB)
    HEATMAP.to_crs(CRS).to_file(FILEPATHB, driver='GPKG', layer=f'heatmap {D}m')

    R = 8192
    XR, YR = hg.get_extent(BOUNDARY, R)
    print(f'Create {C + 1} of {BOUNDARIES.shape[0]}: {XR} x {YR} grid {R}m')
    MESH = hg.get_meshframe(BOUNDARY, CENTRE, R)
    print(dt.datetime.now() - START)
    print(f'Create heatmap {N} connections')
    HEATMAP = get_heatmap(MESH, GEOGRAPHY, 'population', N)

    HEATMAP['class'] = C
    squares = hg.get_squares(hg.get_points(HEATMAP), R / 2.0)
    HEATMAP['geometry'] = [Polygon(v) for v in squares]

    print(dt.datetime.now() - START)
    print('Write heatmap')
    HEATMAP.to_crs(CRS).to_file(FILEPATHB, driver='GPKG', layer=f'heatmap {R}m')

FILEPATH = 'output/heatmap.gpkg'
TOWNS = TOWNS.set_crs(CRS)
FIELDS = ['class', 'area', 'population']
TOWNS[FIELDS] = TOWNS[FIELDS].astype(int)
TOWNS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='towns')

POINTS = hg.get_points(TOWNS)
TRIANGLES = Delaunay(POINTS)

LINES = hg.get_lines(TRIANGLES.simplices, TOWNS['name'].values, POINTS, CRS)
LINES['km'] = LINES.length / 1.0E3

LINES.reset_index().to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='delaunay')
