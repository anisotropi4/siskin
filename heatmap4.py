#!/usr/bin/env python3

import os
import datetime as dt

import pandas as pd
import geopandas as gp

from scipy.spatial import Delaunay

from herbert.base import archive, append_gf
import herbert.geometry as hg
import herbert.people as hp


pd.set_option('display.max_columns', None)

CRS = hg.readupdate_crs('EPSG:32630')

START = dt.datetime.now()

print('Load_boundaries')
FILEPATH = 'bkm64.gpkg'

try:
    BOUNDARIES
except NameError:
    BOUNDARIES = gp.read_file(FILEPATH, layer='fit2 p2 boundary').to_crs(CRS)

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

FILEPATH = 'grid.gpkg'
try:
    GEOGRAPHY
except NameError:
    GEOGRAPHY = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

OUTPATH = 'heatmap.gpkg'
archive(OUTPATH)
CENTRES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='centres')
BOXES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='boundaries')

D = 2048
R = 8192
N = 512

#FILESTUB = os.path.basename(OUTPATH).split('.')[0]
#FILEDIR = os.path.dirname(OUTPATH)

TOWNS = gp.GeoDataFrame(columns=['name', 'class', 'area', 'population', 'geometry'], dtype=int)

for i, boundary in BOUNDARIES.iterrows():
    print(dt.datetime.now() - START)
    #OUTPATH = f'{FILEDIR}/{FILESTUB}-{str(i+1).zfill(2)}.gpkg'
    #archive(OUTPATH)

    centre = hg.get_point(CENTRES.loc[i])

    m, n = hg.get_extent(boundary, R)
    print(f'Create {i + 1} of {BOUNDARIES.shape[0]}: {m} x {n} grid {R}m')
    print(f'Create heatmap {N} connections')
    mesh = hg.get_meshframe(boundary, centre, R)
    heatmap = hp.get_heatmap(mesh, GEOGRAPHY, i, R)
    heatmap = heatmap.rename(columns={'weight': 'p', 'weight2': 'p2'})
    print(dt.datetime.now() - START)
    print('Write heatmap')
    append_gf(heatmap, OUTPATH, f'heatmap {R}m', CRS)

    m, n = hg.get_extent(boundary, D)
    print(f'Create {i + 1} of {BOUNDARIES.shape[0]}: {m} x {n} grid {D}m')
    print(f'Create heatmap {N} connections')
    mesh = hg.get_meshframe(boundary, centre, D)
    heatmap = hp.get_heatmap(mesh, GEOGRAPHY, i, D)
    heatmap = heatmap.rename(columns={'weight': 'p', 'weight2': 'p2'})
    print(dt.datetime.now() - START)
    print('Write heatmap')
    append_gf(heatmap, OUTPATH, f'heatmap {D}m', CRS)

    TOWNS.loc[i, 'class'] = i
    idx1 = gp.clip(GEOGRAPHY['geometry'], boundary['geometry']).index
    FIELDS = ['area', 'population']
    TOWNS.loc[i, FIELDS] = GEOGRAPHY.loc[idx1, FIELDS].sum()
    TOWNS.loc[i, 'name'] = f'C{str(i).zfill(2)}'
    heatframe = hp.get_heatframe(mesh, GEOGRAPHY, 'population', N)
    idx2 = heatframe['weight2'].idxmax()
    TOWNS.loc[i, 'geometry'] = heatframe.loc[idx2, 'geometry']

#OUTPATH = 'output/heatmap.gpkg'
TOWNS = TOWNS.set_crs(CRS)
FIELDS = ['class', 'area', 'population']
TOWNS[FIELDS] = TOWNS[FIELDS].astype(int)
TOWNS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='towns')

POINTS = hg.get_points(TOWNS)
TRIANGLES = Delaunay(POINTS)

LINES = hg.get_lines(TRIANGLES.simplices, TOWNS['name'].values, POINTS, CRS)
LINES['km'] = LINES.length / 1.0E3

LINES.reset_index().to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='delaunay')
