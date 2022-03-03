#!/bin/sh

pip install wheel
cd herbert
python setup.py bdist_wheel
pip install --force-reinstall dist/herbert-0.1.0-py3-none-any.whl 
