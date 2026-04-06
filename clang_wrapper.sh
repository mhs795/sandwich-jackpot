#!/bin/bash
# Strip hostpython3 include paths from NDK cross-compile invocations.
# These host Python headers conflict with NDK sysroot headers on Ubuntu 24.04.
real_compiler="$1"
shift

filtered=()
skip_next=false
for arg in "$@"; do
    if $skip_next; then
        skip_next=false
        continue
    fi
    # Drop -I flags pointing to hostpython3 directories
    if [[ "$arg" == -I* && "$arg" == *hostpython* ]]; then
        continue
    fi
    filtered+=("$arg")
done

# Only inject the compat header for host (non-NDK) builds
if [[ "$real_compiler" == *ndk* ]]; then
    exec "$real_compiler" "${filtered[@]}"
else
    exec "$real_compiler" -include /home/martinstevenson/sandwich_machine/gnuc_compat.h "${filtered[@]}"
fi
