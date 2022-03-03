#!/usr/bin/sh -x

if [ -f heatmap.gpkg ]; then
    rm heatmap.gpkg
fi

ogrinfo output/heatmap.gpkg -sql "VACUUM"

for i in $(seq -w 64)
do
    ogrinfo output/heatmap-${i}.gpkg -sql "VACUUM"
    ogr2ogr -f "gpkg" -append heatmap.gpkg output/heatmap-${i}.gpkg
done

ogr2ogr -f "gpkg" -append heatmap.gpkg output/heatmap.gpkg
ogrinfo heatmap.gpkg -sql "VACUUM"
