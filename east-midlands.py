#!/usr/bin/env python3

import os
import datetime as dt

import pandas as pd
import geopandas as gp
from shapely.geometry import Polygon
from scipy.spatial import cKDTree

from fiona.errors import DriverError

from herbert.base import archive, append_gf
import herbert.geometry as hg
import herbert.people as hp

pd.set_option('display.max_columns', None)

START = dt.datetime.now()

print('Load_boundaries')

CRS = hg.readupdate_crs('EPSG:32630')

FILEPATH = 'bkm64.gpkg'
LAYER = 'fit2 p2 boundary'
try:
    BOUNDARIES
except NameError:
    BOUNDARIES = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

print(dt.datetime.now() - START)
print('Write boundaries centres and boxes')
KEYS = ['class', 'area', 'population']
CENTRES = gp.GeoDataFrame(data=BOUNDARIES[KEYS],
                          geometry=hg.get_centres(BOUNDARIES)).set_crs(CRS)
BOXES = gp.GeoDataFrame(data=BOUNDARIES[KEYS],
                        geometry=BOUNDARIES.envelope).set_crs(CRS)

print(dt.datetime.now() - START)
print(f'Read geography {LAYER}')

FILEPATH = 'grid.gpkg'
LAYER = 'OA'
try:
    GEOGRAPHY
except NameError:
    GEOGRAPHY = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

OUTPATH = 'east-midlands.gpkg'
archive(OUTPATH)
CENTRES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='centres')
BOXES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='boundaries')

R = 128
D = 2048

TOWNS = gp.GeoDataFrame(columns=['name', 'distance', 'p', 'p2',
                                 'area', 'population', 'geometry'], dtype=int)

EMCLASSES = [1, 10, 15, 21, 34, 45, 48]
GF = BOUNDARIES[BOUNDARIES['class'].isin(EMCLASSES)]

FIELDS = ['area', 'population', 'sarea', 'geometry']
GF[FIELDS].dissolve(aggfunc='sum').to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='boundary')

for i, boundary in GF.iterrows():
    #if i != 34:
    #    continue
    print(dt.datetime.now() - START)
    centre = hg.get_point(CENTRES.loc[i])

    N = 32
    n, m = hg.get_extent(boundary, R)
    print(f'Create {i + 1} of {BOUNDARIES.shape[0]}: {n} x {m} grid {R}m')
    mesh = hg.get_meshframe(boundary, centre, R)
    print(dt.datetime.now() - START)
    print(f'Create gridmap {N} connections')
    grid = mesh.sjoin_nearest(GEOGRAPHY, max_distance=8192.0)
    grid['p'] = grid['density'] * R * R / 1.0E6
    grid['p'] = grid['p'] * boundary['population'] / grid['p'].sum()
    heatgrid = hp.get_heatframe(mesh, grid, 'p', N)
    heatgrid = heatgrid.rename(columns={'weight': 'p', 'weight2': 'p2'})
    kscale = boundary['population'] / heatgrid['p'].sum()
    print(f'Ratio v to population {kscale}')
    heatgrid['p'] = heatgrid['p'] * kscale
    heatgrid['class'] = i

    print(dt.datetime.now() - START)
    print('Write gridmap')
    #OUTPATH = f'{FILEDIR}/{FILESTUB}-{str(i+1).zfill(2)}.gpkg'
    #archive(OUTPATH)
    append_gf(heatgrid.to_crs(CRS), OUTPATH, f'gridmap {R}m', CRS)

    heatmap = hp.get_heatmap(mesh, grid, i, R, N, 'p')
    heatmap = heatmap.rename(columns={'weight2': 'p2'})
    heatmap['p'] = heatmap['weight'] * kscale

    print(dt.datetime.now() - START)
    print('Write heatmap')
    append_gf(heatmap.to_crs(CRS), OUTPATH, f'heatmap {R}m', CRS)

    N = 512
    n, m = hg.get_extent(boundary, D)
    print(f'Create {i + 1} of {BOUNDARIES.shape[0]}: {n} x {m} grid {D}m')
    mesh = hg.get_meshframe(boundary, centre, D)
    print(dt.datetime.now() - START)
    print(f'Create heatmap {N} connections')
    heatmap = hp.get_heatmap(mesh, GEOGRAPHY, i, D)
    heatmap = heatmap.rename(columns={'weight': 'p', 'weight2': 'p2'})

    print(dt.datetime.now() - START)
    print('Write heatmap')
    append_gf(heatmap.to_crs(CRS), OUTPATH, f'heatmap {D}m', CRS)

    idx1 = gp.clip(GEOGRAPHY['geometry'], boundary['geometry']).index
    FIELDS = ['area', 'population']
    TOWNS.loc[i, FIELDS] = GEOGRAPHY.loc[idx1, FIELDS].sum()
    idx2 = heatmap['p'].idxmax()
    FIELDS = ['distance', 'p', 'p2']
    TOWNS.loc[i, FIELDS] = heatmap.loc[idx2, FIELDS]
    TOWNS.loc[i, 'geometry'] = mesh.loc[idx2, 'geometry']
    TOWNS['name'] = f'T{str(i).zfill(3)}'

TOWNS['name'] = [f'C{str(i).zfill(3)}' for i in range(1, TOWNS.shape[0] + 1)]
TOWNS = TOWNS.set_crs(CRS)
TOWNS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='cities')

