from setuptools import setup, Extension
from Cython.Build import cythonize
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

MCU_TARGET = os.environ.get("MCU_TARGET", "stm32l4xx")
COMMON_INC = os.environ.get("COMMON_INC",
    os.path.join(ROOT, "lib", "emLibC", "common", "inc"))
PORT_INC   = os.environ.get("PORT_INC",
    os.path.join(ROOT, "lib", "emLibC", "port", "src", "stm", MCU_TARGET))
CORE_INC   = os.path.join(ROOT, "Core", "Inc")
CORE_SRC   = os.path.join(ROOT, "Core", "Src")
COMMON_SRC = os.path.join(ROOT, "lib", "emLibC", "common", "src")
GPIO_SRC = os.path.join(ROOT, "lib", "emLibC", "port", "src")
GPIO_INC = os.environ.get("GPIO_INC", 
    os.path.join(ROOT, "lib", "emLibC", "port", "inc"))

print(f"  COMMON_INC : {COMMON_INC}")
print(f"  PORT_INC   : {PORT_INC}")
print(f"  CORE_INC   : {CORE_INC}")
print(f"  GPIO_INC   : {GPIO_INC}")
print(f"  UNIT_TEST  : aktiviert")

state_ext = Extension(
    name="PyAppliFrame",
    sources=[
        "PyAppliFrame.pyx",
        os.path.join(COMMON_SRC, "state.c"),
        os.path.join(COMMON_SRC, "common.c"),
        os.path.join(CORE_SRC,   "payload.c"),
        #os.path.join(GPIO_SRC,   "_gpio.c"),
        #os.path.join(GPIO_SRC,   "gpio_port.c"),
        os.path.join(CORE_SRC,   "AppliFrame.c"),
    ],
    include_dirs=[COMMON_INC, PORT_INC, GPIO_INC, CORE_INC],
    define_macros=[
        ("UNIT_TEST",   None),
        ("_GNU_SOURCE", None),  # macht isascii() unter -std=c99 sichtbar
    ],
    extra_compile_args=["-O2", "-Wall", "-std=c99"],
)

setup(
    name="emLibC_python",
    version="0.1.0",
    ext_modules=cythonize(
        [state_ext],
        include_path=["."],
        compiler_directives={
            "language_level": "3",
            "embedsignature": True,
            "boundscheck": False,
            "wraparound": False,
        },
    ),
)
