#!/usr/bin/bash -x

${HOME}/miniconda3/bin/python3 -m venv venv
source venv/bin/activate
sudo apt install gdal-bin
pip install wheel
pip install --upgrade pip

pip install -r requirements.txt
