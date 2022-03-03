#!/usr/bin/env python3

import os
import datetime as dt

import numpy as np

import pandas as pd
import geopandas as gp

from shapely.validation import make_valid
from shapely.geometry import LineString, Polygon

from scipy.spatial.distance import pdist

from libpysal.weights import Delaunay, Gabriel
from libpysal.cg import voronoi_frames

import networkx as nx
import momepy

from herbert.base import archive

def get_cityblock(gf1):
    r = gf1.bounds.to_numpy().T
    r = np.diff(r[[0, 2, 1, 3], :].T.reshape(-1, 2, 2))
    return np.abs(r).reshape(-1, 2).sum(1)

def get_pdist(gf1, metric='euclidean', **k):
    s = {'metric': metric, **k}
    r = gf1.bounds.to_numpy().reshape(-1, 2, 2)
    return np.array([pdist(i, **s) for i in r]).reshape(-1)

#ff08E8
pd.set_option('display.max_columns', None)

START = dt.datetime.now()

CRS='EPSG:32630'
print(dt.datetime.now() - START)
print('Load geography')

FILEPATH = 'heatmap.gpkg'
LAYER = 'towns'
print(dt.datetime.now() - START)
print(f'Load {LAYER}')

try:
    CITIES
except NameError:
    CITIES = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)
    CITIES = CITIES.sort_values('population', ascending=False).reset_index(drop=True)

print('Load_boundaries')
LAYER = 'boundaries'
print(dt.datetime.now() - START)
print(f'Load {LAYER}')
try:
    BOUNDARIES
except NameError:
    BOUNDARIES = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

FILEPATH = 'em-grid.gpkg'
LAYER = 'fit boundary p grid 1024'
print(dt.datetime.now() - START)
print(f'Load {LAYER}')

try:
    GRID
except NameError:
    GRID = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

LAYER = 'fit p grid 1024'
print(dt.datetime.now() - START)
print(f'Load {LAYER}')

try:
    CENTRES
except NameError:
    CENTRES = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

print(dt.datetime.now() - START)
#start at 10k population
P = 10.0E3

TOWNS = CENTRES[CENTRES['p'] >= P].sort_values('p', ascending=False).reset_index(drop=True)
TOWNS['population'] = TOWNS['p'].round().astype(int)
TOWNS = TOWNS.rename(columns={'name': 'centre name'})
TOWNS['name'] = 'T' + (TOWNS.index + 1).astype(str).str.zfill(3)

POINTS = TOWNS['geometry']

def get_wnx(gx, points=POINTS):
    try:
        edges = [LineString(points[np.array(i)]) for i in gx.edges]
    except KeyError:
        return get_wnx(gx, points.values)
    return gp.GeoSeries(edges).rename('geometry').set_crs(CRS)

def get_links(df1, df2=TOWNS, k='em class'):
    v = df1[['source', 'target']].to_numpy().reshape(-1)
    return df2.loc[v, k].values.reshape(-1, 2)

def get_paths(mx, links, weight='weight', points=CENTRES):
    r = [nx.shortest_path(mx, *(i), weight=weight) for i in links]
    return [LineString(points.loc[j, 'geometry'].values) for j in r]

print('Create network')
CX = nx.complete_graph(TOWNS.shape[0])
DF1 = nx.to_pandas_edgelist(CX)
DF1[['source name', 'target name']] = TOWNS['name'].values[DF1[['source', 'target']].to_numpy().reshape(-1)].reshape(-1, 2)
GF1 = gp.GeoDataFrame(data=DF1, geometry=get_wnx(CX))
GF1['distance'] = GF1.length

NX = momepy.gdf_to_nx(GF1, approach='primal')

def get_mst(k, network=NX):
    gx = nx.minimum_spanning_tree(network, weight=k)
    nodes, edges = momepy.nx_to_gdf(gx, points=True, lines=True)
    return nodes, edges

FILEPATH = 'network-em.gpkg'
for key in ['distance']:
    _, MST = get_mst(key)
    MST.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer=f'MST {key}')

DS1 = pd.concat([MST['source'], MST['target']]).rename('node').reset_index().groupby('node').count()['index'].rename('n')
DS2 = TOWNS['em class']

GF1['n source'] = DS1.values.reshape(-1)[GF1['source']]
GF1['n target'] = DS1.values.reshape(-1)[GF1['target']]
IDX1 = (GF1['n source'] > 2)
IDX2 = (GF1['n target'] > 2)
GF1['links'] = 0
GF1.loc[IDX1, 'links'] += 1
GF1.loc[IDX2, 'links'] += 1

GF2 = GRID.copy()
GF2['town'] = -1
GF2.loc[DS2, 'town'] = DS2.index
GF2['town name'] = ''
GF2.loc[DS2, 'town name'] = TOWNS.set_index('em class').loc[DS2, 'name'].values

GF2['links'] = 0
GF2.loc[DS2, 'links'] = DS1[GF2.loc[DS2, 'town']].values

EMCITIES = gp.clip(CITIES[['class', 'name', 'geometry']], GRID).set_index('class')

GF3 = TOWNS[['geometry', 'em class']].set_index('em class')
HUBS = gp.sjoin_nearest(GF3, EMCITIES, distance_col='d').sort_values('d').reset_index()
HUBS = HUBS.drop_duplicates('name').rename(columns={'index_right': 'class'})
HUBS = HUBS.set_index('em class').join(GF2[['town', 'town name']]).reset_index()
HUBS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='hubs')

GF2['city'] = -1
GF2.loc[HUBS.set_index('em class').index, 'city'] = HUBS['class'].values
GF2['city name'] = ''
GF2.loc[HUBS.set_index('em class').index, 'city name'] = HUBS['name'].values

GF2.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='grid')

GF4 = GF2.copy()
GF4['geometry'] = CENTRES['geometry']
GF4.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='centres')
IDX4 = GF4['city'] >= 0
GF4[IDX4].to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='cities')
IDX4 = GF4['town'] >= 0
GF4[IDX4].to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='towns')

INNER = GF2['geometry'].apply(make_valid).reset_index().dissolve()
INNER = gp.GeoSeries(INNER.loc[0, 'geometry'].geoms).set_crs(CRS)
INNER = INNER.exterior.apply(Polygon)
INNER = gp.GeoSeries(INNER.iloc[INNER.area.idxmax()]).rename('geometry').set_crs(CRS)
INNER.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='inner')

ENVELOPE = INNER.envelope
ENVELOPE.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='envelope')

OUTER = ENVELOPE.difference(INNER)
OUTER.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='outer')

VORONOI, _  = voronoi_frames(np.stack([CENTRES['geometry'].x, CENTRES['geometry'].y]).T, clip=ENVELOPE[0])
VORONOI = VORONOI.set_crs(CRS)
VORONOI.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='Voronoi')
GF2['geometry'] = gp.clip(VORONOI['geometry'], INNER)
GF2.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='grid2')

EXTERIOR = gp.clip(VORONOI, OUTER).reset_index(drop=True).set_crs(CRS)
EXTERIOR.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='exterior')
EXTERIOR = EXTERIOR.loc[EXTERIOR.area > 5.0E6, ['geometry']]
EXTERIOR['geometry'] = EXTERIOR.centroid
EXTERIOR[['em class', 'p', 'name']] = [-1, 0, 'EXTERIOR']
EXTERIOR.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='exterior points')

NX = pd.concat([CENTRES, EXTERIOR]).reset_index(drop=True)
NX.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='NX')

DELAUNAY = Delaunay.from_dataframe((NX))
DX = DELAUNAY.to_networkx()
DF2 = nx.to_pandas_edgelist(DX)[['source', 'target']]
EDGES = gp.GeoDataFrame(get_wnx(DX, NX['geometry']))
EDGES = EDGES.join(DF2)
EDGES['source'] = NX['em class'].values[EDGES['source']]
EDGES['target'] = NX['em class'].values[EDGES['target']]
EDGES.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='D1')
IDX3 = EDGES[(EDGES['source'] > -1) & (EDGES['target'] > -1)].index
EDGES = EDGES.loc[IDX3]
EDGES['distance'] = EDGES.length
EDGES.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='D2')

MX = nx.from_pandas_edgelist(EDGES, edge_attr='distance')
LINKS = get_links(MST)
PATHS = gp.GeoDataFrame(data=LINKS, columns=['source', 'target'], geometry=get_paths(MX, LINKS, 'distance'))

PATHS = PATHS.set_crs(CRS)
PATHS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='paths')

GABRIEL = Gabriel.from_dataframe(HUBS)
GX = GABRIEL.to_networkx()
DF2 = nx.to_pandas_edgelist(GX)[['source', 'target']]
EDGES = gp.GeoDataFrame(get_wnx(GX, HUBS['geometry']))
EDGES = EDGES.join(DF2)
EDGES['source'] = HUBS['em class'].values[EDGES['source']]
EDGES['target'] = HUBS['em class'].values[EDGES['target']]
EDGES['distance'] = EDGES.length
EDGES.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='GX')

EX = nx.from_pandas_edgelist(EDGES, edge_attr='distance')
LINKS = np.array(EX.edges)
PATHS = gp.GeoDataFrame(data=LINKS, columns=['source', 'target'], geometry=get_paths(MX, LINKS, 'distance'))

PATHS = PATHS.set_crs(CRS)
PATHS.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='routes')
