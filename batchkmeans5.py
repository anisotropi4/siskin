#!/usr/bin/env python3

import os
import datetime as dt
import numpy as np
from joblib import cpu_count

import pandas as pd
import geopandas as gp
from shapely.geometry import Point, LineString, Polygon
from sklearn.cluster import MiniBatchKMeans

from herbert.base import archive, pairwise, scale_series
from herbert.people import get_density
from herbert.geometry import get_points

pd.set_option('display.max_columns', None)

# EPSG:4326 WG 84
# EPSG:32630
# EPSG:27700 OS GB36

pd.set_option('display.max_columns', None)

CRS = 'EPSG:32630'

START = dt.datetime.now()

LAYER = 'OA'
print(f'Load points {LAYER}')
FILEPATH = 'grid.gpkg'

try:
    POINTS
except NameError:
    POINTS = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS).set_index(LAYER)
    POINTS = pd.DataFrame(index=POINTS.index, data=get_points(POINTS))
    POINTS['index'] = range(POINTS.shape[0])

print(f'Read geography {LAYER}')
try:
    GEOGRAPHY
except NameError:
    GEOGRAPHY = gp.read_file('geography.gpkg', layer=LAYER).to_crs(CRS)

print(dt.datetime.now() - START)
print('Create model')

CLUSTER = MiniBatchKMeans(
    init="k-means++",
    n_clusters=64,
    batch_size=256 * cpu_count(),
    n_init=64,
    max_no_improvement=128,
    verbose=0,
    random_state=0,
)
print(dt.datetime.now() - START)

WEIGHTS = {'base' : [1.0 for i in range(POINTS.index.shape[0])],
           'dp' : scale_series(GEOGRAPHY['density'] * GEOGRAPHY['population']),
           'dp2' : (scale_series(GEOGRAPHY['density'] * GEOGRAPHY['population'])) ** 2,
           'ia' : scale_series(1.0 / GEOGRAPHY['area']),
           'p' : scale_series(GEOGRAPHY['population']),
           'p2' : scale_series(GEOGRAPHY['population']) ** 2,
}

WEIGHTS = {'p2' : scale_series(GEOGRAPHY['population']) ** 2, }

FILEPATH = 'bkm64.gpkg'
archive(FILEPATH)

KEY = None
for k, WEIGHT in WEIGHTS.items():
    KEY = k
    print(f'Fit model {k}')
    CLUSTER.fit(POINTS[[0, 1]], '', WEIGHT)
    print(dt.datetime.now() - START)
    LABELS = CLUSTER.labels_
    GEOGRAPHY['class'] = LABELS

    print('Write model')
    print(dt.datetime.now() - START)
    KEYS = ['area', 'population', 'class']
    DATA = GEOGRAPHY[KEYS].groupby('class').sum().reset_index()
    CENTRES = gp.GeoDataFrame(DATA, geometry=[Point(i) for i in CLUSTER.cluster_centers_]).set_crs(CRS)
    CENTRES.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'fit {k}')
print(dt.datetime.now() - START)

print('Find boundaries')
KEYS = ['area', 'population', 'geometry', 'class']
BKM = GEOGRAPHY[KEYS].dissolve(by='class', aggfunc='sum')

print(dt.datetime.now() - START)
print('Write boundaries')
BKM = BKM.reset_index()

BKM.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'fit {KEY} boundary')
print(dt.datetime.now() - START)
print(f'Find towns {KEY}')
#KEYS = ['class', 'population']
#KEYS = ['class', 'density']
LSOA = gp.read_file('geography.gpkg', layer='LSOA').to_crs(CRS)
LSOA['geometry'] = LSOA.centroid
CENTROIDS = LSOA.set_index('LSOA')['geometry']

KEYS = ['class', 'geometry']
TOWNS = BKM[KEYS].sjoin(LSOA, how='inner', predicate='intersects')
TOWNS = TOWNS.sort_values(['class', 'density']).drop_duplicates(subset='class', keep='last')
TOWNS['geometry'] = CENTROIDS.loc[TOWNS['LSOA'].values].values
KEYS = ['class', 'LSOA', 'MSOA', 'Country', 'geometry']
TOWNS = TOWNS[KEYS]
KEYS = ['population', 'area']
TOWNS = TOWNS.join(BKM[KEYS], on='class')
TOWNS['density'] = get_density(TOWNS)

TOWNS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'town points {KEY}')
