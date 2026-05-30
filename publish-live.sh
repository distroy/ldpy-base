#! /usr/bin/env bash
#
# Copyright (C) distroy
#


set -ex

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"; pwd)"
cd "$SOURCE_DIR"

rm -rf ./dist


# pip3 install build twine
python3 -m build --no-isolation
twine check dist/*
twine upload dist/*
