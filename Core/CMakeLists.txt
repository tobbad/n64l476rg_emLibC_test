cmake_minimum_required(VERSION 3.22)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)

project(stm32l476rg_emLibC)
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_C_COMPILER arm-none-aebi-gcc)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

add_library(libstm32l476rg STATIC
    Drivers/STM32Lxx_HAL_Driver/src/stm32l4xx_hal.c
    Drivers/STM32Lxx_HAL_Driver/src/stm32l4xx_hal_cortex.c
    Drivers/STM32Lxx_HAL_Driver/src/stm32l4xx_hal_gpio.c
    Drivers/STM32Lxx_HAL_Driver/src/stm32l4xx_hal_rcc.c
    Drivers/STM32Lxx_HAL_Driver/src/stm32l4xx_hal_uart.c
    Drivers/STM32Lxx_HAL_Driver/src/stm32l4xx_hal_uart_ex.c
    Drivers/STM32Lxx_HAL_Driver/src/stm32l4xx_hal_uart_ex.c
    Core/Startup/startup_stm32l476rgtx.s)

target_include_directories(stm32l476rg_emLibC PUBLIC
    Drivers/STM32Lxx_HAL_Driver/Inc/
    Drivers/CMSIS/Include/
    Drivers/CMSIS/Device/ST/STM32L4xx/Include
)


target_compile_options(hello_world PUBLIC
    -mcpu cortex=m4
    -mthumb
)
target_compile_definitions(
    USE_HAL_DRIVER
    STM32L476xx
)
t
add_custom_target(run_in_renode
    COMMAND renode --console --disable-wxt -e "include &${CMAKE_CURRENT_SOURCE_DIR/run_hello_world.resc}"
    DEPENDS stm32l476rg_emLibC
)
