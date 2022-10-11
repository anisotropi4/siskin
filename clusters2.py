#!/usr/bin/env python3
"""Ab initio transport network based on population distribution"""
import datetime as dt
import argparse

import numpy as np

import pandas as pd
import geopandas as gp

from shapely.geometry import LineString

#from scipy.spatial.distance import pdist

from libpysal.weights import Delaunay

from sklearn.cluster import AgglomerativeClustering

import networkx as nx
from networkx.utils import pairwise
#from networkx.algorithms.flow import maximum_flow_value

import herbert.geometry as hg

#ff08E8
pd.set_option('display.max_columns', None)

#start at 10k population
P = 10.0E3
REGION = 'wales'
REGION = 'wessex'
REGION = 'em'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='create ab initio transport network based on population distribution')
    parser.add_argument('region', type=str, help='region name',
                        nargs='?', default='em')
    parser.add_argument('-p', dest='population', type=float,
                        help='population centre', default=10.0E3)

    args = parser.parse_args()
    P = args.population
    REGION = args.region

START = dt.datetime.now()

CRS='EPSG:32630'

OUTPATH = f'clusters-{REGION}-{int(P / 1.0E3)}k.gpkg'

FILEPATH = f'{REGION}-grid.gpkg'
LAYER = 'fit p grid 1024'
print(dt.datetime.now() - START)
print(f'Load {LAYER}')

try:
    GRID
except NameError:
    GRID = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

LAYER = 'fit boundary p grid 1024'
print(dt.datetime.now() - START)
print(f'Load {LAYER}')
try:
    BOUNDARY
except NameError:
    BOUNDARY = gp.read_file(FILEPATH, layer=LAYER).to_crs(CRS)

def get_convexhull(boundary):
    gf = boundary.copy()
    gf['geometry'] = gf.convex_hull
    return gf

print('Get 1km clipped boundary')
def get_clipped(this_gf, d1=128.0, d2=-1024.0):
    gf = this_gf.buffer(d1, single_sided=True).buffer(d2, single_sided=True)
    gf = gf.rename('geometry').reset_index()
    return this_gf.overlay(gf, how='union').dissolve()

try:
    OUTER
except NameError:
    OUTER = get_clipped(BOUNDARY.dissolve())

EXTERIOR = OUTER.explode(index_parts=False).iloc[0]['geometry']
OUTER.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='outer')

print(dt.datetime.now() - START)

print('Get convex hull boundaries')
HBOUNDARY = get_convexhull(BOUNDARY)
HBOUNDARY.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='hboundary')

del BOUNDARY
print(dt.datetime.now() - START)
print('Get clipped boundary')

ALLBOUNDARIES = gp.clip(HBOUNDARY, OUTER.loc[0, 'geometry'])
ALLBOUNDARIES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='allboundary')
HGRID = ALLBOUNDARIES.copy()
HGRID['geometry'] = HGRID.centroid

HGRID.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='hgrid')

print(dt.datetime.now() - START)

print('Get towns')
pIDX = HGRID[HGRID['p'] > 10.0E3].index

print(dt.datetime.now() - START)
print('agglomerate clusters')

def agglomerate_cluster(this_index, points, d):
    ACF = AgglomerativeClustering(n_clusters=None,
                                  distance_threshold=d,
                                  linkage='ward',
                                  compute_distances=True)
    this_fit = ACF.fit(points)
    return pd.Series(index=this_index, data=this_fit.labels_)

def get_clusters(boundary, p_index, grid, d=65536.0):
    """ returns GeoDataFrames with cluster extent and point with largest population
    """
    gf1 = boundary.copy()
    gf1['class'] = -1
    points = hg.get_points(grid.loc[p_index])
    gf1.loc[p_index, 'class'] = agglomerate_cluster(p_index, points, d)
    gf2 = gf1.loc[gf1['class'] >= 0, ['class', 'geometry']].dissolve(by='class')
    gf2 = gf2.explode(index_parts=False).reset_index()
    gf2['cluster'] = gf2.index
    gf3 = gp.sjoin(grid[['geometry', 'p']], gf2).drop(columns='index_right')

    gf1 = gf1.loc[gf3.index]
    gf1.loc[gf3.index, 'cluster'] = gf3['cluster']
    gf1 = gf1[['p', 'geometry', 'cluster']].dissolve(by='cluster', aggfunc='sum').reset_index()
    gf1['name'] = 'T' + (gf1.index + 1).map(str).str.zfill(3)

    gf2 = gf3.reset_index().rename(columns={'index': 'em class'})
    gf2 = gf2.sort_values(['cluster', 'p']).drop_duplicates(subset='cluster', keep='last')
    gf2 = gf2.reset_index(drop=True).drop(columns='class')
    gf2[['name', 'population']] = gf1[['name', 'p']]
    return (gf1, gf2)

print(dt.datetime.now() - START)
print('Get clusters and nodes')

CLUSTERS, NODES = get_clusters(ALLBOUNDARIES, pIDX, HGRID)

CLUSTERS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='clusters')
NODES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='nodes')

def get_wnx(gx, points):
    try:
        edges = [LineString(points[np.array(i)]) for i in gx.edges]
    except KeyError:
        return get_wnx(gx, points.values)
    return gp.GeoSeries(edges).rename('geometry').set_crs(CRS)

def get_paths(mx, links, weight='weight', points=HGRID):
    r = []
    for link in links:
        try:
            r.append(nx.shortest_path(mx, *(link), weight=weight))
        except nx.exception.NodeNotFound:
            r.append([])
    return [LineString(points.loc[j, 'geometry'].values) for j in r]

print(dt.datetime.now() - START)
print('Get cluster Delaunay network')
DELAUNAY = Delaunay.from_dataframe(NODES)

DX = DELAUNAY.to_networkx().to_directed()
EDGES = gp.GeoDataFrame(get_wnx(DX, NODES['geometry']))

DS4 = NODES.set_index('cluster')['em class']
EDGES[['source', 'target']] = np.asarray(DX.edges)
EDGES[['em source', 'em target']] = DS4.values[np.asarray(DX.edges)]
EDGES['distance'] = EDGES.length

EDGES = gp.GeoDataFrame(EDGES).set_crs(CRS)
EDGES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='edges')

print(dt.datetime.now() - START)
print('Get full Delaunay network')
DELAUNAY = Delaunay.from_dataframe((HGRID))
DX = DELAUNAY.to_networkx()
DF2 = nx.to_pandas_edgelist(DX)[['source', 'target']]
ALLPATHS = gp.GeoDataFrame(get_wnx(DX, HGRID['geometry']))
ALLPATHS = ALLPATHS.join(DF2)
ALLPATHS['source'] = HGRID['em class'].values[ALLPATHS['source']]
ALLPATHS['target'] = HGRID['em class'].values[ALLPATHS['target']]
ALLPATHS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='D1')

print(dt.datetime.now() - START)
print('Clip Delaunay network')
IDX1 = ALLPATHS.crosses(EXTERIOR)
ALLPATHS = ALLPATHS.loc[~IDX1]
ALLPATHS['distance'] = ALLPATHS.length
ALLPATHS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='D2')

print(dt.datetime.now() - START)
print('Get shortest-path cluster network')
FIELDS = ['source', 'target', 'em source', 'em target']
MX = nx.from_pandas_edgelist(ALLPATHS, edge_attr='distance')
PX = get_paths(MX, EDGES[['em source', 'em target']].values, 'distance')
DEDGES = gp.GeoDataFrame(data=EDGES, columns=FIELDS, geometry=PX).set_crs(CRS)
DEDGES['distance'] = DEDGES.length
DEDGES.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='droutes')

def get_path_list(mx, links, weight='weight'):
    return [nx.shortest_path(mx, *(i), weight=weight) for i in links]

IDX7 = DEDGES.set_index(['source', 'target']).index
LX = nx.MultiDiGraph([(*IDX7[i], {'leg': k, 'id': i})
               for i, j in enumerate(
                       get_path_list(MX, EDGES[['em source', 'em target']].values, 'distance'))
               for k in pairwise(j)])

print(dt.datetime.now() - START)
print('Create network legs')

DF4 = nx.to_pandas_edgelist(LX)
GB1 = DF4[['leg', 'id']].groupby('leg').count().rename(columns={'id': 'count'})
DF4 = DF4.join(GB1, on='leg')
DF4[['em source', 'em target']] = DF4['leg'].apply(pd.Series)
DF4 = DF4.set_index('leg')

DF4['direction'] = 'U'
IDX8 = DF4['source'] > DF4['target']
DF4.loc[IDX8, 'direction'] = 'D'

LEGS = gp.GeoDataFrame(index=DF4.index, geometry=get_paths(MX, DF4.index, 'distance'), data=DF4)
LEGS = LEGS.reset_index(drop=True).set_crs(CRS)
LEGS['distance'] = LEGS.length
LEGS.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='dd2')

FIELDS = ['source', 'target', 'em source', 'em target', 'distance']
DF6 = DEDGES[FIELDS].copy()

DF6['p*p'] = NODES['p'].values[DF6[['source', 'target']]].prod(axis=1)
DF6['p+p'] = NODES['p'].values[DF6[['source', 'target']]].sum(axis=1)
DF6['capacity'] = (DF6['p*p']).astype(int)
DF6['capacity'] = (DF6['p+p']).astype(int)
DF6['capacity'] = (1.0E6 / DF6['distance']).astype(int)
DF6['capacity'] = (DF6['p*p'] / DF6['distance']).astype(int)

FX = nx.from_pandas_edgelist(DF6, edge_attr=['capacity'], create_using=nx.DiGraph)

print(dt.datetime.now() - START)
print('Calculate network flow')

DF6['pfp'] = 0.0

DF6 = DF6.set_index(['source', 'target'])
LEGS = LEGS.set_index(['source', 'target'])

FIELDS = ['em source', 'em target', 'count', 'direction', 'distance']
DF7 = pd.DataFrame(data=LEGS[FIELDS], index=LEGS.index, columns=FIELDS+list(range(DF6.shape[0])), )

for i, k in enumerate(DF6.index):
    R = nx.flow.preflow_push(FX, *k)
    #R = nx.flow.edmonds_karp(FX, *k)
    DF6.loc[k, 'pfp'] = R.graph['flow_value']
    ds = nx.to_pandas_edgelist(R).set_index(['source', 'target'])['flow']
    ds[ds < 0] = 0
    DF7.loc[ds.index, i] = ds

print(dt.datetime.now() - START)
print('Create network segments')

DF6 = DF6.reset_index()
DF7 = DF7.reset_index()

DF7['sum'] = DF7[list(range(DF6.shape[0]))].sum('columns')

GF8 = gp.GeoDataFrame(data=DF6, geometry=DEDGES['geometry'])
GF8 = GF8.set_crs(CRS)
GF8.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='segments')

LEGS = LEGS.reset_index()
GF9 = gp.GeoDataFrame(data=DF7, geometry=LEGS['geometry'])
GF9 = GF9.set_crs(CRS)
GF9.columns = [str(i) for i in GF9.columns]
GF9.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='legs')

print(dt.datetime.now() - START)
print('Calculate network route')

GF10 = gp.GeoDataFrame(data=DF7, geometry=LEGS['geometry'])
GF10 = GF10.set_crs(CRS)
GF10[['em source', 'em target']] = np.array(
    LEGS[['em source', 'em target']].apply(sorted, axis=1).to_list())
GF10.columns = [str(i) for i in GF10.columns]
#SCALE = 2 * (DF6['p*p'] * DF6['p*p']).sum() / (DF6['distance'] * DF6['distance']).sum()
SCALE = 2 * (DF6['p*p']).sum() / (DF6['distance']).sum()
GF10['scale'] = GF10['sum'] / SCALE
GF10.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='routes')

print(dt.datetime.now() - START)
print('Calculate network sum')

M = GF10.shape[1]
FIELDS = GF10.columns.take(list(range(7, M))).insert(0, 'em source').insert(1, 'em target')
DF8 = GF10[FIELDS].groupby(['em source', 'em target']).sum()

LEGS = LEGS.set_index(['em source', 'em target'])
GF11 = gp.GeoDataFrame(DF8.join(LEGS[['source', 'target', 'count', 'geometry']]))
LEGS = LEGS.reset_index()
GF11 = GF11.reset_index()
GF11['direction'] = 'B'
GF11['distance'] = GF11.length
GF11 = GF11[GF10.columns]
GF11.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='sum')

print(dt.datetime.now() - START)
print('Calculate network scale')

GF11['scale'] = GF11['sum'] / SCALE
GF11.to_crs(CRS).to_file(OUTPATH, driver='GPKG', layer='scale')
