#!/bin/bash
python -m nuitka ./elbear_uploader.py \
--output-dir=build_linux \
--output-filename="elbear_uploader" \
--standalone

cd build_linux
mv elbear_uploader.dist elbear_uploader
tar -czvf elbear_uploader_linux.tar.gz elbear_uploader
