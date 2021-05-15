#!/bin/sh

echo "Unit testing..."
coverage run --source=src -m unittest discover tests && coverage report -m