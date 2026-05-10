#!/bin/bash
git log --pretty=format:'const char* git_hash= "git hash=[%H]";' -n 1 > ../Core/Src/githash.c
OUT_HEADER="../Core/Inc/githash.h"
GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
{
echo "/*"
echo " * githash.h"
echo " *"
echo " *  Created on: $(date +"%b %d, %Y")"
echo " *      Author: badi"
echo " */"
echo "#ifndef INC_GITHASH_H_"
echo "#define INC_GITHASH_H_"
echo
echo "// Git Hash des Builds"
printf '#define GIT_HASH "%s"\n' "$GIT_HASH"
echo
echo "extern const char* git_hash;"
echo
echo "#endif /* INC_GITHASH_H_ */"
} > $OUT_HEADER
