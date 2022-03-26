#!/usr/bin/bash
source venv/bin/activate
export PYTHONUNBUFFERED=1

export PATH=./bin:${PATH}

for i in archive data download output SHP
do
    if [ ! -d ${i} ]; then
        mkdir ${i}
    fi
done

echo Download Scotland mid-year estimates 2020
FILE=sape-20-all-tabs-and-figs.zip
if [ ! -s data/${FILE} ]; then
    echo here
    URL='https://www.nrscotland.gov.uk/files//statistics/population-estimates/sape-20/'
    curl -o data/${FILE} "${URL}/${FILE}"
fi

if [ ! -s data/Mid-2020-scotland.csv ]; then
    unzip -c data/${FILE} sape-20-all-tabs-and-figs_TabA.csv | tail -n +5 | head -n -3 > data/Mid-2020-scotland.csv
fi

FILE=OA_DZ_IZ_2011.xlsx
if [ ! -s data/${FILE} ]; then
    URL='https://www.nrscotland.gov.uk/files//geography/2011-census/'
    curl -o data/${FILE} "${URL}/${FILE}"
fi

FILE=OA-DZ-lookup.tsv
if [ ! -s data/${FILE} ]; then
    FILEPATH=data/OA_DZ_IZ_2011.xlsx
    ./xl2tsv.py --tab "OA_DZ_IZ_2011 Lookup" --path data --noempty ${FILEPATH}
    mv "data/OA_DZ_IZ_2011 Lookup.tsv" data/${FILE}
fi

echo Try England and Wales mid-year estimates 2020
if [ $(ls data/sape23dt10* 2> /dev/null | wc -l) -lt 10 ]   
then
    echo Download England and Wales mid-year estimates 2020
   ./download-ew.py
fi

for FILEPATH in $(ls data/sape23dt10*.xlsx)
do
    STUB=$(basename ${FILEPATH} | sed 's/^.*estimates\(.*\).xlsx$/\1/')
    echo Processing ${STUB}
    FILE=Mid-2020-${STUB}.tsv
    if [ ! -s data/${FILE} ]; then
        ./xl2tsv.py --tab "Mid-2020 Persons" --path data --noempty ${FILEPATH}
        tail -n +3 "data/Mid-2020 Persons.tsv" > data/${FILE}
    fi
    if [ -f "data/Mid-2020 Persons" ]; then
        rm "data/Mid-2020 Persons"
    fi
done

FILE=OA-MS-LS.csv
if [ ! -s data/${FILE} ]; then
    URI='http://geoportal1-ons.opendata.arcgis.com/datasets/fe6c55f0924b4734adf1cf7104a0173e_0.csv'
    curl -L -o data/${FILE} "${URI}"
fi

echo Download Scotland MHW OA geography

FILE=output-area-2011-mhw.zip
if [ ! -s data/${FILE} ]; then    
    URL="https://www.nrscotland.gov.uk/files/geography/"
    curl -o data/${FILE} ${URL}/${FILE}
fi

STUB=OutputArea2011_MHW
if [ ! -s data/${STUB}.shp ]; then
    (cd data; unzip ${FILE})
fi

FILE=OA-2011-boundaries-SC-BFC.gpkg
if [ ! -s data/${FILE} ]; then
    ogr2ogr -f GPKG data/${FILE} data/${STUB}.shp -t_srs EPSG:32630
fi

echo Download England and Wales MHW OA geography
FILE=OA-2011-boundaries-EW-BFC.geojson
if [ ! -s data/${FILE} ]; then
    URI="https://services1.arcgis.com/ESMARspQHYMw9BZ9/ArcGIS/rest/services/Output_Areas_December_2011_Boundaries_EW_BFC/FeatureServer/0"
    esri2geojson ${URI} data/${FILE}
fi

FILE=OA-2011-boundaries-EW-BFC.gpkg
if [ ! -s data/${FILE} ]; then
    STUB=$(echo ${FILE} | sed 's/.gpkg$//')
    ogr2ogr -f GPKG data/${STUB}.gpkg data/${STUB}.geojson -t_srs EPSG:32630
fi

FILE=OA-2011-boundaries-SC-BFC.gpkg
if [ ! -s data/${FILE} ]; then
    STUB=$(echo ${FILE} | sed 's/.gpkg$//')
    ogr2ogr -f GPKG data/${STUB}.gpkg data/${STUB}.geojson 
fi

if [ ! -s geography.gpkg ]; then
    ./geography.py
fi

if [ ! -s bkm64.gpkg ]; then
    ./batchkmeans5.py
fi

if [ ! -s heatmap.gpkg ]; then
    ./heatmap4.py
    ./heatmaps.sh
fi

if [ ! -s east-midlands.gpkg ]; then
    ./east-midlands.py
    ./eastmidlands.sh
fi

if [ ! -s em-grid.gpkg ]; then
    ./batchkmeans-em.py
fi

if [ ! -s network-em.gpkg ]; then
    ./network-em3.py
fi

if [ ! -s SHP/routes.shp ]; then
    ogr2ogr SHP/ network-em.gpkg -t_srs EPSG:4277
fi
