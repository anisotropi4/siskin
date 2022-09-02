#!/usr/bin/env python3

import datetime as dt
from joblib import cpu_count

import numpy as np

import pandas as pd
import geopandas as gp

from sklearn.cluster import MiniBatchKMeans
from libpysal.cg import voronoi_frames

from herbert.base import scale_series
import herbert.geometry as hg

pd.set_option('display.max_columns', None)

# EPSG:4326 WG 84
# EPSG:32630
# EPSG:27700 OS GB36

pd.set_option('display.max_columns', None)

START = dt.datetime.now()

CRS='EPSG:32630'
FILEPATH = 'east-midlands.gpkg'

LAYER = 'gridmap 128m'
print(f'Load {LAYER}')

try:
    GRID
except NameError:
    GRID = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

LAYER = 'boundary'
try:
    BOUNDARY
except NameError:
    BOUNDARY = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

POINTS = hg.get_points(GRID)
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

WEIGHTS = {'p' : scale_series(GRID['p']), 'p2' : scale_series(GRID['p']) ** 2,}
WEIGHTS = {'p' : scale_series(GRID['p']), }

OUTPATH = 'em-grid.gpkg'
for k, weight in WEIGHTS.items():
    print(f'Fit model {k} number of clusters {N}')
    CLUSTER.fit(POINTS, '', weight)
    print(dt.datetime.now() - START)
    labels = CLUSTER.labels_
    GRID['em class'] = labels
    GRID['name'] = [f'C{str(i).zfill(4)}' for i in (labels + 1)]
    print('Write model')
    print(dt.datetime.now() - START)
    KEYS = ['p', 'em class']
    DATA = GRID[KEYS].groupby('em class').sum().reset_index()
    DS1 = GRID.set_index('em class')['name'].drop_duplicates()
    DATA = DATA.join(DS1, on='em class')
    P = CLUSTER.cluster_centers_
    CENTRES = gp.GeoDataFrame(data=DATA, geometry=gp.points_from_xy(*(P.T))).set_crs(CRS)
    CENTRES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'fit {k} grid {N}')
    POINTS = np.asarray(CENTRES['geometry'].apply(lambda v: np.array(v.xy)).to_list()).reshape(-1, 2)
    FIELDS = ['em class', 'p', 'name']
    VORONOI, _ = voronoi_frames(POINTS, clip=BOUNDARY.envelope[0])
    VORONOI = gp.clip(VORONOI.set_crs(CRS), BOUNDARY['geometry']).sort_index()
    VORONOI[FIELDS] = DATA[FIELDS]
    VORONOI.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'fit boundary {k} grid {N}')

print(dt.datetime.now() - START)
