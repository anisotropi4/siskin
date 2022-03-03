#!/usr/bin/env python3

import os
import datetime as dt
from itertools import cycle, tee
import numpy as np
from joblib import cpu_count

import pandas as pd
import geopandas as gp
from shapely.geometry import LineString, Polygon

from sklearn.cluster import MiniBatchKMeans

from herbert.base import archive, scale_series
import herbert.geometry as hg

pd.set_option('display.max_columns', None)

# EPSG:4326 WG 84
# EPSG:32630
# EPSG:27700 OS GB36

pd.set_option('display.max_columns', None)

START = dt.datetime.now()

LAYER = 'gridmap 128m'
print(f'Load {LAYER}')
CRS='EPSG:32630'
FILEPATH = 'east-midlands.gpkg'

try:
    GRID
except NameError:
    GRID = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

POINTS = hg.get_points(GRID.centroid)

print(dt.datetime.now() - START)
print('Create model')
N = 1024
#N = 58

CLUSTER = MiniBatchKMeans(
    init="k-means++",
    n_clusters=N,
    batch_size=256 * cpu_count(),
    n_init=64,
    max_no_improvement=128,
    verbose=0,
    random_state=0,
)
print(dt.datetime.now() - START)

WEIGHTS = {'p' : scale_series(GRID['p']),
           'p2' : scale_series(GRID['p']) ** 2,}

WEIGHTS = {'p' : scale_series(GRID['p']), }

FILEPATHB = 'em-grid.gpkg'
for k, WEIGHT in WEIGHTS.items():
    print(f'Fit model {k} number of clusters {N}')
    CLUSTER.fit(POINTS, '', WEIGHT)
    print(dt.datetime.now() - START)
    LABELS = CLUSTER.labels_
    GRID['em class'] = LABELS
    GRID['name'] = [f'C{str(i).zfill(4)}' for i in (LABELS + 1)]
    print('Write model')
    print(dt.datetime.now() - START)
    KEYS = ['p', 'em class']
    DATA = GRID[KEYS].groupby('em class').sum().reset_index()
    DS1 = GRID.set_index('em class')['name'].drop_duplicates()
    DATA = DATA.join(DS1, on='em class')
    P = CLUSTER.cluster_centers_
    CENTRES = gp.GeoDataFrame(data=DATA, geometry=gp.points_from_xy(*(P.T))).set_crs(CRS)
    CENTRES.to_crs(CRS).to_file(FILEPATHB, driver='GPKG', layer=f'fit {k} grid {N}')
    KEYS = ['p', 'em class', 'geometry']
    BKM = GRID[KEYS].dissolve(by='em class', aggfunc='sum')
    BKM = BKM.join(DS1)
    BKM.to_crs(CRS).to_file(FILEPATHB, driver='GPKG', layer=f'fit boundary {k} grid {N}')

print(dt.datetime.now() - START)
