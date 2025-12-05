#!/usr/bin/env bash

mkdir -p ./natKit/api/build/python/natKit/codegen/api
touch ./natKit/api/build/python/natKit/__init__.py
touch ./natKit/api/build/python/natKit/codegen/__init__.py
touch ./natKit/api/build/python/natKit/codegen/api/__init__.py
protoc -I=./natKit/api/src/proto/natKit/api/ --python_out=./natKit/api/build/python/natKit/codegen/api/ --proto_path=./natKit/api/src/proto/natKit/api/ schema.proto
