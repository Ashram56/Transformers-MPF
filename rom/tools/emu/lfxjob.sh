#!/bin/sh
# lfxjob.sh NAME MODE ids...  -> lfx/NAME.log with a fresh NVRAM
D=$(dirname $(realpath $0)); S=$D/..; N=$1; shift
V=$(mktemp -d); mkdir -p $V/roms; ln -s $HOME/.pinmame/roms/tf_180.zip $V/roms/
VPM_DIR=$V PINMAME_NOJIT=1 timeout 3000 $D/lfx $S/lfx/$N.log "$@" 2> $S/lfx/$N.err
rm -rf $V
