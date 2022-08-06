# siskin
An approach to the creation of an ab initio transport network model for Great Britain

## Population and Geography

Base population geography if from latest mid-year 2020 population estimates for Scotland, England and Wales.

The census geography is projected on to a [Universal Transverse Mercator (UTM)](https://en.wikipedia.org/wiki/Universal_Transverse_Mercator_coordinate_system) coordinate system to allow distance and area calculations in metres, rather than longitude/latitude. Using the [European Petroleum Survey Group](https://en.wikipedia.org/wiki/EPSG_Geodetic_Parameter_Dataset) [EPSG 32630 projection](https://epsg.io/32630) for the UK. Following devolution, population estimates for England and Wales, and Scotland are maintained separately, and the different Scots Data-Zone (DZ) and English and Welsh Output Area (OA) census geographies are mapped.

### Scotland
Download Scotland mid-year population estimates 2020 in Data-Zones (DZ) and map to the 2011 Census Output Area (OA) geographies

1.   Extract the Data-Zone 2020 mid-year population estimates data from National Records of Scotland zip archive [here](https://www.nrscotland.gov.uk/files/statistics/population-estimates/sape-20/) and extract the Data-Zone data population estimates into a `CSV` file
2.   Map the Data-Zone and OutputArea using the National Records of Scotland lookup file [here](https://www.nrscotland.gov.uk/files/geography/2011-census/OA_DZ_IZ_2011.xlsx)
3.   Download the 2011 ESRI ShapeFile Output Area Mid-Half-Water (MHW) census geography from National Records of Scotland [here](https://www.nrscotland.gov.uk/files/geography/output-area-2011-mhw.zip)
4.   Project the shapefile census geography to a `EPSG:32630` format `GeoPackage` file


### England and Wales
Download the latest mid-year population estimates in 2011 Census Output Area (OA) geographies from the Office of National Statistics (ONS). The OA mid-year population estimate data for England is split into nine region.

1.    Page scrape, download and extract the Output Area 2020 mid-year population estimates data for the ONS regions in England and Wales under [here](https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates#datasets) in `XLSX` format into 10 `TSV` files
2.   Download the 2011 ESRI ShapeFile Output Area Mid-Half-Water (MHW) census geography in `GeoJSON` from Office of National Statistics ArcGIS API server [here](https://services1.arcgis.com/ESMARspQHYMw9BZ9/ArcGIS/rest/services/Output_Areas_December_2011_Boundaries_EW_BFC/FeatureServer/0)
4.   Project the shapefile census geographies to a `EPSG:32630` format `GeoPackage` file

### Combine Population and Geography

The Output Area (OA) population boundary is created by transforming the Scots from Data-Zone to OA and combining this with the English and Wales to create an OA layer `GeoPackage` file. Combining this OA data to create Super Output Area (LSOA) and Middle Super Output Area (MSOA) layers, see ONS coding systems [here](https://en.wikipedia.org/wiki/ONS_coding_system), Additional OA centroid and Great Britain boundary layers.



