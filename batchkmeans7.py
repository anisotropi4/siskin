#!/usr/bin/env python3

import datetime as dt
from joblib import cpu_count

import pandas as pd
import geopandas as gp
from sklearn.cluster import MiniBatchKMeans

from herbert.base import archive, scale_series
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

FILEPATH = 'geography.gpkg'
print(f'Read geography {LAYER}')
try:
    GEOGRAPHY
except NameError:
    GEOGRAPHY = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)
    POINTS = pd.DataFrame(index=GEOGRAPHY['OA'], data=get_points(GEOGRAPHY.centroid))
    POINTS['index'] = range(POINTS.shape[0])

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

WEIGHTS = {'base' : list(range(POINTS.index.shape[0])),
           'p' : scale_series(GEOGRAPHY['population']),
           'p2' : scale_series(GEOGRAPHY['population']) ** 2,
           'dp' : scale_series(GEOGRAPHY['density'] * GEOGRAPHY['population']),
           'dp2' : (scale_series(GEOGRAPHY['density'] * GEOGRAPHY['population'])) ** 2,
           'ia' : scale_series(1.0 / GEOGRAPHY['area']),
}

WEIGHTS = {'p2' : scale_series(GEOGRAPHY['population']) ** 2, }

FILEPATH = 'bkm64.gpkg'
archive(FILEPATH)
print(dt.datetime.now() - START)

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
    CENTRES = gp.GeoDataFrame(DATA, geometry=gp.points_from_xy(*CLUSTER.cluster_centers_.T)).set_crs(CRS)
    CENTRES.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'fit {k}')
print(dt.datetime.now() - START)

print('Find boundaries')
KEYS = ['area', 'population', 'geometry', 'class']
BKM = GEOGRAPHY[KEYS].dissolve(by='class', aggfunc='sum')

print('Write boundaries')
BKM = BKM.reset_index()
BKM.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'fit {KEY} boundary')

print(dt.datetime.now() - START)
print('Find boundaries 2')
SPLIT = BKM.explode(index_parts=True)
SPLIT['sarea'] = SPLIT.area
SPLIT['key'] = 0
IDX1 = (SPLIT['sarea'] > 1.0E6) & (SPLIT['sarea'] < 5.0E8)
SPLIT.loc[IDX1, 'key'] = SPLIT[IDX1].reset_index().index + 1

SPLIT = SPLIT.sort_values(['class', 'sarea'], ascending=False)
IDX2 = SPLIT.drop_duplicates(subset='class').index
SPLIT.loc[IDX2, 'key'] = 0
SPLIT = SPLIT.sort_index()
IDX3 = SPLIT['key'] == 0

GF1 = SPLIT[IDX3].dissolve(by='class', aggfunc='first').reset_index()
GF1['sarea'] = GF1.area
GF1['key'] = GF1['class']
GF2 = SPLIT[~IDX3].reset_index(drop=True)
BKM2 = GF1.copy()

print(dt.datetime.now() - START)

for i, region in GF2.iterrows():
    gf = gp.GeoDataFrame([region], crs=CRS)
    idx = GF1[GF1.touches(region['geometry'])].index
    
    if len(idx) == 0:
        idx = pd.Index([region['class']])
    if len(idx) > 1:
        gs = GF1.loc[idx].intersection(region['geometry']).length
        idx = gs.sort_values(ascending=False).index.take([0])
    GF2.loc[i, 'key'] = idx.values[0]
    #BKM2.loc[idx] = pd.concat([BKM2.loc[idx], gf]).dissolve().set_index(idx)

BKM2 = pd.concat([GF1, GF2]).dissolve(by='key', aggfunc='first')
BKM2['area'] = BKM2.area

POPULATION = gp.GeoDataFrame(data=GEOGRAPHY['population'], geometry=GEOGRAPHY.centroid)

GF3 = gp.sjoin(BKM2[['class', 'geometry']], POPULATION, how='left')
DF1 = GF3[['class', 'population']].groupby('class').sum()
BKM2['population'] = DF1

IDX4 = POPULATION.index.difference(GF3.set_index('index_right').index)
GF4 = gp.sjoin_nearest(POPULATION.loc[IDX4], BKM2[['class', 'geometry']], how='left')
DF2 = GF4[['class', 'population']].groupby('class').sum()
BKM2.loc[DF2.index, 'population'] += DF2['population']

print(dt.datetime.now() - START)
print('Write boundaries')
BKM2.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'fit2 {KEY} boundary')

print(dt.datetime.now() - START)
print(f'Find towns {KEY}')
#KEYS = ['class', 'population']
#KEYS = ['class', 'density']
LSOA = gp.read_file('grid.gpkg', layer='LSOA').to_crs(CRS)
MSOA = gp.read_file('grid.gpkg', layer='MSOA').to_crs(CRS)

KEYS = ['class', 'geometry']
TOWNS = MSOA.sjoin(BKM2[KEYS], predicate='within').drop(columns='index_right')
TOWNS = TOWNS.sort_values(['class', 'density']).drop_duplicates(subset='class', keep='last')

KEYS = ['class', 'MSOA', 'Country', 'geometry']
TOWNS = TOWNS[KEYS]
KEYS = ['population', 'area']
TOWNS = TOWNS.join(BKM2[KEYS], on='class')
TOWNS['density'] = get_density(TOWNS)

TOWNS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'MSOA town d points {KEY}')
# MSOA density gives the best locations
TOWNS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'town points {KEY}')

KEYS = ['class', 'geometry']
TOWNS = LSOA.sjoin(BKM2[KEYS], predicate='within').drop(columns='index_right')
TOWNS = TOWNS.sort_values(['class', 'density']).drop_duplicates(subset='class', keep='last')

KEYS = ['class', 'LSOA', 'MSOA', 'Country', 'geometry']
TOWNS = TOWNS[KEYS]
KEYS = ['population', 'area']
TOWNS = TOWNS.join(BKM2[KEYS], on='class')
TOWNS['density'] = get_density(TOWNS)

TOWNS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'LSOA town d points {KEY}')

KEYS = ['class', 'geometry']
TOWNS = MSOA.sjoin(BKM2[KEYS], predicate='within').drop(columns='index_right')
TOWNS = TOWNS.sort_values(['class', 'population']).drop_duplicates(subset='class', keep='last')

KEYS = ['class', 'MSOA', 'Country', 'geometry']
TOWNS = TOWNS[KEYS]
KEYS = ['population', 'area']
TOWNS = TOWNS.join(BKM2[KEYS], on='class')
TOWNS['density'] = get_density(TOWNS)

TOWNS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'MSOA town p points {KEY}')

KEYS = ['class', 'geometry']
TOWNS = LSOA.sjoin(BKM2[KEYS], predicate='within').drop(columns='index_right')
TOWNS = TOWNS.sort_values(['class', 'population']).drop_duplicates(subset='class', keep='last')

KEYS = ['class', 'LSOA', 'MSOA', 'Country', 'geometry']
TOWNS = TOWNS[KEYS]
KEYS = ['population', 'area']
TOWNS = TOWNS.join(BKM2[KEYS], on='class')
TOWNS['density'] = get_density(TOWNS)

TOWNS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'LSOA town p points {KEY}')

print(dt.datetime.now() - START)
