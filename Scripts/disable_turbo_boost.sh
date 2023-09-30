#!/bin/bash
set -e

echo "Disabling Turbo Boost."
wrmsr -a 0x1a0 0x4000850089

