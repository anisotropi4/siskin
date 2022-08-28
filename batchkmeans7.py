#!/usr/bin/env python3

import datetime as dt
from joblib import cpu_count

import pandas as pd
import geopandas as gp
from shapely.geometry import Polygon
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

OUTPATH = 'bkm64.gpkg'
archive(OUTPATH)
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
    CENTRES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'fit {k}')
print(dt.datetime.now() - START)

print('Find boundaries')
KEYS = ['area', 'population', 'geometry', 'class']
BKM = GEOGRAPHY[KEYS].dissolve(by='class', aggfunc='sum')
print('Write boundaries')
BKM = BKM.reset_index()

print('Find boundaries 2')
SPLIT = BKM.explode(index_parts=True)
SPLIT = SPLIT.reset_index()
SPLIT['sarea'] = SPLIT.area
IDX1 = SPLIT['sarea'] > 5.0E7
BOUNDARIES = SPLIT.loc[IDX1]
BOUNDARIES['geometry'] = BOUNDARIES['geometry'].apply(lambda v: Polygon(v.exterior))
SPLIT['key'] = SPLIT['class']

centres = SPLIT.loc[SPLIT.index.difference(IDX1)]
centres['geometry'] = centres.centroid

# Move centres back inside boundaries
for k, v in BOUNDARIES.iterrows():
    idx = centres[centres['class'] != v['class']].within(v['geometry'])
    for m in idx[idx].index:
        SPLIT.loc[m, 'key'] = v['class']

SPLIT['class'] = SPLIT['key']
KEYS = ['class', 'geometry']
BKM = SPLIT[KEYS].dissolve(by='class', aggfunc='first')
BKM['area'] = BKM.area

POPULATION = gp.GeoDataFrame(data=GEOGRAPHY['population'], geometry=GEOGRAPHY.centroid)
DF1 = BKM.reset_index()[['class', 'geometry']].sjoin(POPULATION).groupby('class').sum()
BKM['population'] = DF1['population']

BKM.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'fit {KEY} boundary')

print(dt.datetime.now() - START)
print('Find boundaries 3')

# migrate sub-regions to largest shared border rather than BKM boundary
SPLIT = BKM.explode(index_parts=True).reset_index()
SPLIT['sarea'] = SPLIT.area
SPLIT['key'] = SPLIT['class']

# only migrate sub-regions between 10^6 and 10^9 m^2
IDX1 = (SPLIT['sarea'] > 1.0E6) & (SPLIT['sarea'] < 5.0E8)
IDX1 = IDX1[IDX1].index
IDX2 = SPLIT.index.difference(IDX1)

GF1 = SPLIT.loc[IDX2].dissolve(by='class', aggfunc='first').reset_index()
GF1['sarea'] = GF1.area

GF2 = SPLIT.loc[IDX1].reset_index(drop=True)

print(dt.datetime.now() - START)
for i, region in GF2.iterrows():
    gf = gp.GeoDataFrame([region], crs=CRS)
    idx = GF1[GF1.touches(region['geometry'])].index
    if len(idx) == 0:
        continue
    gs = GF1.loc[idx].intersection(region['geometry']).length
    m = gs.sort_values(ascending=False).index.take([0]).values[0]
    GF2.loc[i, 'key'] = m

GF2['class'] = GF2['key']

# migrate sub-regions to closest region
KEYS = ['class', 'geometry', 'key']
BKM2 = pd.concat([GF1[KEYS], GF2[KEYS]]).dissolve(by='class', aggfunc='first')

SPLIT = BKM2.explode(index_parts=True).reset_index()
SPLIT['sarea'] = SPLIT.area

IDX3 = SPLIT[SPLIT['sarea'] > 1.0E8].index
#IDX3 = SPLIT.sort_values(['class', 'sarea']).drop_duplicates(subset='class', keep='last').index

GF3 = SPLIT.loc[IDX3].dissolve(by='class').reset_index()
IDX4 = SPLIT.index.difference(IDX3)
GF4 = SPLIT.loc[IDX4]

for i, region in GF4.iterrows():
    m = GF3.distance(region['geometry'].centroid).idxmin()
    if SPLIT.loc[i, 'class'] != GF3.loc[m, 'class']:
        SPLIT.loc[i, 'class'] = GF3.loc[m, 'class']

BKM2 = SPLIT.dissolve(by='class', aggfunc='first').reset_index()
BKM2['area'] = BKM2.area

GF5 = gp.sjoin(BKM2[['class', 'geometry']], POPULATION, how='left')
DF1 = GF5[['class', 'population']].groupby('class').sum()
BKM2['population'] = DF1

IDX5 = POPULATION.index.difference(GF5.set_index('index_right').index)
GF6 = gp.sjoin_nearest(POPULATION.loc[IDX5], BKM2[['class', 'geometry']], how='left')
DF2 = GF6[['class', 'population']].groupby('class').sum()
BKM2.loc[DF2.index, 'population'] += DF2['population']

print(dt.datetime.now() - START)
print('Write boundaries')
BKM2.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'fit2 {KEY} boundary')

print(dt.datetime.now() - START)
print(f'Find towns {KEY}')

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

TOWNS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'MSOA town d points {KEY}')
# MSOA density gives the best locations
TOWNS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'town points {KEY}')

KEYS = ['class', 'geometry']
TOWNS = LSOA.sjoin(BKM2[KEYS], predicate='within').drop(columns='index_right')
TOWNS = TOWNS.sort_values(['class', 'density']).drop_duplicates(subset='class', keep='last')

KEYS = ['class', 'LSOA', 'MSOA', 'Country', 'geometry']
TOWNS = TOWNS[KEYS]
KEYS = ['population', 'area']
TOWNS = TOWNS.join(BKM2[KEYS], on='class')
TOWNS['density'] = get_density(TOWNS)

TOWNS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'LSOA town d points {KEY}')

KEYS = ['class', 'geometry']
TOWNS = MSOA.sjoin(BKM2[KEYS], predicate='within').drop(columns='index_right')
TOWNS = TOWNS.sort_values(['class', 'population']).drop_duplicates(subset='class', keep='last')

KEYS = ['class', 'MSOA', 'Country', 'geometry']
TOWNS = TOWNS[KEYS]
KEYS = ['population', 'area']
TOWNS = TOWNS.join(BKM2[KEYS], on='class')
TOWNS['density'] = get_density(TOWNS)

TOWNS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'MSOA town p points {KEY}')

KEYS = ['class', 'geometry']
TOWNS = LSOA.sjoin(BKM2[KEYS], predicate='within').drop(columns='index_right')
TOWNS = TOWNS.sort_values(['class', 'population']).drop_duplicates(subset='class', keep='last')

KEYS = ['class', 'LSOA', 'MSOA', 'Country', 'geometry']
TOWNS = TOWNS[KEYS]
KEYS = ['population', 'area']
TOWNS = TOWNS.join(BKM2[KEYS], on='class')
TOWNS['density'] = get_density(TOWNS)

TOWNS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer=f'LSOA town p points {KEY}')

print(dt.datetime.now() - START)
