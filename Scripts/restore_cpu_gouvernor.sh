#!/bin/bash
set -e

DEFAULT_MIN_FREQ=1.2Ghz
DEFAULT_MAX_FREQ=3.0Ghz

echo "Changing cpu frequency governor to on schedutil."
cpupower frequency-set -g powersave

echo "Enabling all processos idle states."
cpupower idle-set -E

echo "Setting CPU frequency to default values."
cpupower frequency-set -d $DEFAULT_MIN_FREQ -u $DEFAULT_MAX_FREQ
