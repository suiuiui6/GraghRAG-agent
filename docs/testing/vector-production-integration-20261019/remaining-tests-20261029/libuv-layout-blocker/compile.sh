set -eu
for v in old new; do
 x86_64-w64-mingw32-gcc-win32 -std=c11 -I/input/$v/include -c /input/fixture.c -o /work/$v.o
 x86_64-w64-mingw32-objcopy --dump-section .layout=/output/$v.bin /work/$v.o
 cp /work/$v.o /output/$v.o
 x86_64-w64-mingw32-objdump -s -j .layout /work/$v.o > /output/$v.objdump.txt
done
