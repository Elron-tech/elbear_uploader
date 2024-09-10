#!/bin/bash

source venv/bin/activate
python -m nuitka ./elbear_uploader.py \
--output-dir=build \
--output-filename="elbear_uploader" \
--standalone

cd build
mv elbear_uploader.dist elbear_uploader
tar -czvf elbear_uploader_linux.tar.gz elbear_uploader
