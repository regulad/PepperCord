#!/bin/bash

install-pkg python3.10 python3.10-distutils python3.10-dev ffmpeg git

python3.10 -m pip install -r requirements.txt

clear

python3.10 --version
python3.10 main.py
