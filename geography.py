#!/usr/bin/env python3

import os

import pandas as pd
import geopandas as gp

from shapely.validation import make_valid
from shapely.geometry import Polygon

from herbert.base import archive
from herbert.people import get_density

pd.set_option('display.max_columns', None)

# EPSG:4326 WG 84
# EPSG:32630
# EPSG:27700 OS GB36

print('Load OA data')
print('Load Scotland data')
DF0 = pd.read_csv('data/OA-DZ-lookup.tsv', sep='\t')
KEYS = {'IntermediateZone2011Code': 'MSOA', 'DataZone2011Code': 'DataZone2011Code'}
DF0 = DF0[KEYS.keys()].rename(columns=KEYS).drop_duplicates()
DF0 = DF0.set_index('DataZone2011Code')

DF1 = pd.read_csv('data/Mid-2020-scotland.csv')
DF1 = DF1.dropna(axis=1, how='all').dropna(axis=0).reset_index(drop=True)

# Guess OA population values for Scotland
KEYS = {'DataZone2011Code': 'Zone', 'Total population': 'population'}
DS1 = DF1[KEYS.keys()].rename(columns=KEYS).set_index('Zone')['population']
DS1 = DS1.str.replace(',', '').astype(int)

CRS='EPSG:32630'
SCB = gp.read_file('data/OA-2011-boundaries-SC-BFC.gpkg')
SCB = SCB.to_crs(CRS)
KEYS = {'DataZone': 'Zone', 'Popcount': 'population'}
DS2 = SCB[KEYS.keys()].rename(columns=KEYS).set_index('Zone').groupby('Zone').sum()
DS2 = DS2[DS2.index.isin(DS1.index)]['population']

SC1 = pd.Series(index=DS1.index, data=DS1.values / DS2.values, name='s')
SCB['population'] = SCB['Popcount'] * SCB.join(SC1, on='DataZone').fillna(1.0)['s']
SCB['population'] = SCB['population'] * DS1.sum() / SCB['population'].sum()
SCB['population'] = SCB['population'].round().astype(int)

SCB = SCB.join(DF0, on='DataZone')
SCB['Country'] = 'Scotland'

print('Mid-year population error: {}'.format(abs(SCB['population'].sum() - DS1.sum())))
KEYS = {'code': 'OA', 'DataZone': 'LSOA', 'SHAPE_1_Ar': 'area'}
FIELDS = ['OA', 'LSOA', 'MSOA', 'Country', 'area', 'population']
POPULATION = SCB.rename(columns=KEYS)[FIELDS]
FIELDS = ['OA', 'Country', 'geometry']
GEOGRAPHY = SCB.rename(columns=KEYS)[FIELDS]
del SCB

print('Load England & Wales data')
DF0 = pd.read_csv('data/OA-MS-LS.csv')
KEYS = {'OA11CD': 'OA',
        'LSOA11CD': 'LSOA',
        'LSOA11NM': 'LSOA name',
        'MSOA11CD': 'MSOA',
        'MSOA11NM': 'MSOA name',
        'CTRY11NM': 'Country'}
DF0 = DF0[KEYS.keys()].rename(columns=KEYS).drop_duplicates()
FIELDS = ['OA', 'LSOA', 'MSOA', 'Country']
DF2 = DF0[FIELDS].set_index('OA')

print('Load England & Wales geography')
EWB = gp.read_file('data/OA-2011-boundaries-EW-BFC.gpkg')
print('Re-project England & Wales geography')
EWB = EWB.to_crs(CRS)
EWB = EWB.join(DF2, on='OA11CD')

KEYS = {'OA11CD': 'OA', 'Shape__Area': 'area'}
FIELDS = ['OA', 'LSOA', 'MSOA', 'Country', 'area', 'geometry']
EWB = EWB.rename(columns=KEYS)[FIELDS]

DS3 = EWB.set_index('OA')['area']

print('Load England & Wales population')
KEYS = {'OA11CD': 'OA', 'All Ages': 'population'}
FIELDS = ['OA', 'LSOA', 'MSOA', 'Country', 'area', 'population']
for r in ['eastmidlands', 'east', 'london', 'northeast',
          'northwest', 'southeast', 'southwest', 'wales',
          'westmidlands', 'yorkshireandthehumber']:
    DF1 = pd.read_csv(f'data/Mid-2020-{r}.tsv', sep='\t')
    DF1 = DF1.join(DF2, on='OA11CD').join(DS3, on='OA11CD')
    DF1 = DF1.rename(columns=KEYS)[FIELDS]
    POPULATION = pd.concat([POPULATION, DF1])

POPULATION['density'] = get_density(POPULATION)
POPULATION = POPULATION.sort_values(['OA']).reset_index(drop=True)

FIELDS = ['OA', 'Country', 'geometry']
GEOGRAPHY = pd.concat([GEOGRAPHY, EWB[FIELDS]])
GEOGRAPHY = GEOGRAPHY.sort_values('OA').reset_index(drop=True)

del EWB

FIELDS = ['LSOA', 'MSOA', 'area', 'population', 'density']
GEOGRAPHY = GEOGRAPHY.join(POPULATION.set_index('OA')[FIELDS], on='OA')

FIELD = 'population'
GEOGRAPHY[FIELD] = GEOGRAPHY[FIELD].fillna(0).astype(int)
FIELDS = ['OA', 'LSOA', 'MSOA', 'Country', 'area', 'population', 'density', 'geometry']
GEOGRAPHY = GEOGRAPHY[FIELDS]

print('Write GB geography')

print('Create grid')
CENTROID = GEOGRAPHY.set_index('OA').centroid.rename('geometry')
GRID = gp.GeoDataFrame(POPULATION.join(CENTROID.rename('geometry'), on='OA'))

print('Write grid')
GRIDPATH = 'grid.gpkg'
archive(GRIDPATH)
GRID.to_crs(CRS).to_file(GRIDPATH, driver='GPKG', layer='OA')
del GRID

print('Write Geography')
FILEPATH = 'geography.gpkg'
archive(FILEPATH)

print('Write OA geography')
GEOGRAPHY.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='OA')

print('Aggregate LSOA geography')
FIELDS = ['LSOA', 'area', 'population', 'geometry']
LSOA = GEOGRAPHY[FIELDS].dissolve(by='LSOA', aggfunc='sum')
LSOA['density'] = get_density(LSOA)
KEYS = ['LSOA', 'MSOA', 'Country']
DS4 = POPULATION[KEYS].drop_duplicates().set_index('LSOA')
LSOA = LSOA.join(DS4).reset_index()
FIELDS = ['LSOA', 'MSOA', 'Country', 'area', 'population', 'density', 'geometry']
LSOA = LSOA[FIELDS]
del GEOGRAPHY

print('Write LSOA geography')
LSOA.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='LSOA')

CENTROID = LSOA.centroid.rename('geometry')
LSOA.drop('geometry', axis=1).join(CENTROID).to_crs(CRS).to_file(GRIDPATH, driver='GPKG', layer='LSOA')

print('Aggregate MSOA geography')
MSOA = LSOA.dissolve(by='MSOA', aggfunc='sum')
MSOA['density'] = get_density(MSOA)
KEYS = ['MSOA', 'Country']
DS5 = POPULATION[KEYS].drop_duplicates().set_index('MSOA')
MSOA = MSOA.join(DS5).reset_index()
FIELDS = ['MSOA', 'Country', 'area', 'population', 'density', 'geometry']
MSOA = MSOA[FIELDS]

print('Write MSOA geography')
MSOA.to_crs(CRS).to_file(FILEPATH, driver='GPKG', layer='MSOA')

CENTROID = MSOA.centroid.rename('geometry')
MSOA.drop('geometry', axis=1).join(CENTROID).to_crs(CRS).to_file(GRIDPATH, driver='GPKG', layer='MSOA')

print(f'Write GB outline')
OUTER = MSOA['geometry'].apply(make_valid)
OUTER = OUTER.reset_index().dissolve()
OUTER = OUTER.explode(ignore_index=True).drop(columns='index')
OUTER['geometry'] = OUTER.exterior
OUTER['geometry'] = OUTER['geometry'].apply(Polygon)
OUTER['area'] = OUTER.area
OUTER = OUTER.sort_values('area', ascending=False).reset_index(drop=True)

BRITAIN = OUTER[OUTER['area'] > 1.0E8].copy()
BRITAIN['geometry'] = BRITAIN.simplify(10, preserve_topology=False)
GS1 = BRITAIN['geometry'].simplify(100)
BRITAIN = BRITAIN[GS1.distance(GS1[0]) < 2.0E3]
BRITAIN = BRITAIN.dissolve()
BRITAIN.to_file('britain.gpkg', driver='GPKG', layer='outer')

GS2 = OUTER.centroid
G = BRITAIN.loc[0, 'geometry']
IDX1 = GS2.within(G)
OUTER = OUTER.loc[IDX1]

OUTER.to_file(FILEPATH, driver='GPKG', layer='outer')
