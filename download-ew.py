#!/usr/bin/env python

import os.path
from urllib.parse import urlparse, urlunparse
import requests
from bs4 import BeautifulSoup

def download_data(URL):
    r = requests.get(URL)
    soup = BeautifulSoup(r.content, 'html.parser')
    path = None
    for hit in soup.findAll('a'):
        href = hit.get('href')
        if 'xlsx' in href:
            path = href
            break
    if not path:
        return False
    filestub = path.split('/')[-1]
    filepath = f'data/{filestub}'
    if os.path.isfile(filepath):
        return False
    with open(filepath, 'wb') as fout:
        uri = urlunparse(urlparse(URL)._replace(path=path))
        r = requests.get(uri)
        fout.write(r.content)
    return True

BASEURL = 'https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/datasets'

REGIONS = ['london', 'east', 'eastmidlands', 'northeast', 'northwest',
           'southeast', 'southwest', 'westmidlands', 'yorkshireandthehumber']

for REGION in REGIONS:
    URL = f'{BASEURL}/censusoutputareaestimatesinthe{REGION}regionofengland'
    download_data(URL)

URL = f'{BASEURL}/censusoutputareaestimatesinwales'
download_data(URL)
