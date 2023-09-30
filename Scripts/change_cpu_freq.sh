#!/bin/bash
set -e

echo "Changing cpu frequency governor."
cpupower frequency-set -g performance

echo "Disabling all processos idle states."
cpupower idle-set -D 0

echo "Setting CPU frequency to $1."
cpupower frequency-set -d $1 -u $1

