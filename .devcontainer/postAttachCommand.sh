#!/bin/bash

set -e # Add pipe fail command to exit on error

printf "=====< Setting up pre-commits >=====\n\n"
sudo pre-commit install
printf "=====< Setting up pre-commits is done >=====\n\n"
