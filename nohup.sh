#!/usr/bin/bash
source venv/bin/activate
export PYTHONUNBUFFERED=1

#time ./agg.py
#time ./optics.py
#time ./batchkmeans5.py
#time ./heatmap4.py
#time ./east-midlands.py
#time ./batchkmeans-em.py
#time ./network-em.py
time ./tobler-heatmap2.py
#time ./tobler-heatmap3.py
