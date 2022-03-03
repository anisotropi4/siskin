#!/usr/bin/sh -x

if [ -f east-midlands.gpkg ]; then
    rm east-midlands.gpkg
fi

ogrinfo output/east-midlands.gpkg -sql "VACUUM"

for i in 02 11 16 22 35 46 49
do
    ogrinfo output/east-midlands-${i}.gpkg -sql "VACUUM"
    ogr2ogr -f "gpkg" -append east-midlands.gpkg output/east-midlands-${i}.gpkg
done

ogr2ogr -f "gpkg" -append east-midlands.gpkg output/east-midlands.gpkg
ogrinfo east-midlands.gpkg -sql "VACUUM"
