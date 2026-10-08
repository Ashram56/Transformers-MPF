#!/bin/sh
D=$(dirname $0); P=$D/../pinmame
g++ -O2 -std=c++17 -I$P/src/libpinmame $D/$1.cpp -o $D/$1 -L$P/build -lpinmame -Wl,-rpath,$(realpath $P/build) -lpthread
