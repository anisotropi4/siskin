#!/usr/bin/env python3

import os
import datetime as dt
from itertools import product

import numpy as np
import pandas as pd
import geopandas as gp
from shapely.geometry import Polygon
from scipy.spatial import cKDTree

from herbert.base import archive
import herbert.geometry as hg

pd.set_option('display.max_columns', None)

START = dt.datetime.now()

print('Load_boundaries')
FILEPATH = 'bkm64.gpkg'

CRS = hg.readupdate_crs('EPSG:32630')

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

FILEPATH = 'output/east-midlands.gpkg'
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
    if (d == 0.0).any():
        d = d.T[1:].T
        i = i.T[1:].T

    u = 1.0E3 / d.sum(1)
    v = (1.0 * weights.values[i] / d).sum(1)
    w = (1.0 * weights.values[i] * weights.values[i] / d).sum(1)
    return gp.GeoDataFrame(data={'distance': u, 'weight': v, 'weight2': w},
                           geometry=points['geometry']).set_crs(CRS)

D = 2048

TOWNS = gp.GeoDataFrame(columns=['name', 'distance', 'weight', 'weight2',
                                 'area', 'population', 'geometry'], dtype=int)

EMCLASSES = [1, 10, 15, 21, 34, 45, 48]
IDX0 = BOUNDARIES[BOUNDARIES['class'].isin(EMCLASSES)].index

for C, BOUNDARY in BOUNDARIES.loc[IDX0].iterrows():
    print(dt.datetime.now() - START)
    CENTRE = hg.get_point(CENTRES.loc[C])

    XR, YR = hg.get_extent(BOUNDARY, D)
    print(f'Create {C + 1} of {BOUNDARIES.shape[0]}: {XR} x {YR} grid {D}m')

    MESH = hg.get_meshframe(BOUNDARY, CENTRE, D)
    N = 512
    print(dt.datetime.now() - START)
    print(f'Create heatmap {N} connections')
    HEATMAP = get_heatmap(MESH, GEOGRAPHY, 'population', N)
    HEATMAP['class'] = C

    idx1 = gp.clip(GEOGRAPHY['geometry'], BOUNDARY['geometry']).index

    FIELDS = ['area', 'population']
    TOWNS.loc[C, FIELDS] = GEOGRAPHY.loc[idx1, FIELDS].sum()
    idx2 = HEATMAP['weight'].idxmax()
    FIELDS = ['distance', 'weight', 'weight2', 'geometry']
    TOWNS.loc[C, FIELDS] = HEATMAP.loc[idx2, FIELDS]
    TOWNS['name'] = f'T{str(C).zfill(3)}'
    squares = hg.get_squares(hg.get_points(HEATMAP), D / 2.0, 0.2)
    HEATMAP['geometry'] = [Polygon(v) for v in squares]

    print(dt.datetime.now() - START)
    print('Write heatmap')
    FILEPATHB = f'{FILEDIR}/{FILESTUB}-{str(C+1).zfill(2)}.gpkg'
    archive(FILEPATHB)
    HEATMAP.to_crs(CRS).to_file(FILEPATHB, driver='GPKG', layer=f'heatmap {D}m')

    R = 128
    N = 32
    XR, YR = hg.get_extent(BOUNDARY, R)
    print(f'Create {C + 1} of {BOUNDARIES.shape[0]}: {XR} x {YR} grid {R}m')

    MESH = hg.get_meshframe(BOUNDARY, CENTRE, R)
    print(dt.datetime.now() - START)
    print(f'Create gridmap {N} connections')
    GRID = MESH.sjoin_nearest(GEOGRAPHY, max_distance=8192.0)
    GRID['p'] = GRID['density'] * R * R / 1.0E6
    GRID['p'] = GRID['p'] * BOUNDARY['population'] / GRID['p'].sum()
    HEATMAP = get_heatmap(MESH, GRID, 'p', 32)
    K = BOUNDARY['population'] / HEATMAP['weight'].sum()

    print(f'Ratio v to population {K}')
    HEATMAP['p'] = HEATMAP['weight'] * K
    HEATMAP['class'] = C
    squares = hg.get_squares(hg.get_points(HEATMAP), R / 2.0, 0.2)
    HEATMAP['geometry'] = [Polygon(v) for v in squares]

    print(dt.datetime.now() - START)
    print('Write gridmap')
    HEATMAP.to_crs(CRS).to_file(FILEPATHB, driver='GPKG', layer=f'gridmap {R}m')

TOWNS['name'] = [f'C{str(i).zfill(3)}' for i in range(1, TOWNS.shape[0] + 1)]
TOWNS = TOWNS.set_crs(CRS)
TOWNS.to_crs(CRS).to_file(FILEPATHB, driver='GPKG', layer='cities')
