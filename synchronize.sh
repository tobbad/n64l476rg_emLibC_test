#!/bin/bash
SRC_DIR="."
FILES_TO_COPY=(
    "Core/Src/payload.c"
    "Core/Inc/payload.h"
    "Core/Inc/rb_system.h"
    "Core/Src/rb_syste.c"
    "Core/Inc/AppliFrame.h"
    "Core/Src/AppliFrame.c"
    "Core/Src/radio.c"
    "Core/Inc/radio.h"
#    "Core/Src/persistent.c"
    "Core/Inc/persistent.h"
    "Makefile"
    "preBuildScript.sh"
    "restore.sh"
    "zip_sources.sh"
    ".clang-format"
    ".clang-format-ignore"
    ".clang-tidy"
    ".gitignore"
#    "X-CUBE-SUBG2/App/app_x-cube-subg2.h"
#    "X-CUBE-SUBG2/App/app_x-cube-subg2.c"
#    "X-CUBE-SUBG2/Target/s2lp_management.c"
#    "X-CUBE-SUBG2/App/p2p_demo_settings.h"
)
#    "Drivers/BSP/S2868A2/s2868a2.c"
#    "Drivers/BSP/S2868A2/s2868a2.h"
#    "Drivers/BSP/Components/S2LP/s2lp.c"
#    "Drivers/BSP/Components/S2LP/s2lp.h"
#    "Drivers/BSP/Components/S2LP/S2LP_CORE_SPI.h"

# --- Funktion zum Kopieren der Dateien ---

copy_files () {
    local src="$1"
    local dst="$2"
    shift 2
    local files=("$@")

    echo "Kopiere Dateien von $src nach $dst ..."

    for file in "${files[@]}"; do
         echo "Kopiere: $src/$file nach $dst/$file"
         cp "$src/$file" "$dst/$file"
    done

    echo "Fertig!"
}


DST_DIR=( 
    "../radio_bell_stm32l476rg/"
#    "../n64f401re_s2lp_p2p/"
#    "../n64f401re_s2lp_p2p_orig"
#    "../n64l476rg_radioBell_basic_feature"
#    "../n64l476rg_radio_bell" 
#    "../n64l476rg_radio_bell_I"
#    "../n64l476rg_s2lp_p2p"
#    "../n64l476rg_s2lp_p2p_ref"
#    "../n64l476rg_s2lp_p2p_ref_xchange"
)

for trgt  in "${DST_DIR[@]}"; do
    copy_files "$SRC_DIR" "$trgt" "${FILES_TO_COPY[@]}"
done
