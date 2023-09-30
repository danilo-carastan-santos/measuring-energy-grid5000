#!/bin/bash
set -e

echo "Enabling Turbo Boost."
wrmsr -a 0x1a0 0x850089

