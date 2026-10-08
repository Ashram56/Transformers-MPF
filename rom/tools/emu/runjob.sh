#!/bin/sh
# runjob.sh NAME MODE DUR [deff ids...]  -> caps/NAME.log caps/NAME.dmd, fresh NVRAM per run
D=$(dirname $(realpath $0)); S=$D/..; N=$1; shift
V=$(mktemp -d); mkdir -p $V/roms; ln -s $HOME/.pinmame/roms/tf_180.zip $V/roms/
VPM_DIR=$V PINMAME_NOJIT=1 timeout 1500 $D/tracer "$1" "$2" $S/caps/$N.log $S/caps/$N.dmd $(shift 2; echo "$@") 2> $S/caps/$N.err
rm -rf $V
