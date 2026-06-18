cmake_minimum_required(VERSION 3.15)
project(crimson_starfish_bridge)

# 1. Set up Python and nanobind
find_package(Python 3.8 REQUIRED COMPONENTS Interpreter Development.Module)

execute_process(
    COMMAND "${Python_EXECUTABLE}" -c "import nanobind; print(nanobind.cmake_dir())"
    OUTPUT_VARIABLE nanobind_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
find_package(nanobind CONFIG REQUIRED)

# 2. Define CRIMSON and Dependency Paths
set(CRIMSON_ROOT "/home/sadid/crimson/cfs_reg/CRIMSONFlowsolver") # <-- Change this to your CRIMSON root directory
set(CRIMSON_DEPS "/home/sadid/crimson/deps/installs") # <-- Change this to where you installed CRIMSON dependencies (petsc, boost, openblas, etc.)
# This is where your .a files live
set(CRIMSON_LIB_DIR "${CRIMSON_ROOT}/lib")

# Python 2.7 runtime used by CRIMSON parameter controllers
set(CRIMSON_PYTHON_ROOT "/home/sadid/miniconda3/envs/flow")
set(CRIMSON_PYTHON_EXECUTABLE "${CRIMSON_PYTHON_ROOT}/bin/python")
set(CRIMSON_PYTHON_INCLUDE_DIR "${CRIMSON_PYTHON_ROOT}/include/python2.7")
set(CRIMSON_PYTHON_LIBRARY_DIR "${CRIMSON_PYTHON_ROOT}/lib")

# Validate the Python 2.7 runtime required by CRIMSON controllers
if(NOT EXISTS "${CRIMSON_PYTHON_EXECUTABLE}")
    message(FATAL_ERROR "CRIMSON Python executable not found")
endif()

if(NOT EXISTS "${CRIMSON_PYTHON_INCLUDE_DIR}/Python.h")
    message(FATAL_ERROR "CRIMSON Python 2.7 headers not found")
endif()

find_library(
    CRIMSON_PYTHON_LIBRARY
    NAMES python2.7
    PATHS "${CRIMSON_PYTHON_LIBRARY_DIR}"
    NO_DEFAULT_PATH
)

if(NOT CRIMSON_PYTHON_LIBRARY)
    message(FATAL_ERROR "CRIMSON Python 2.7 library not found")
endif()

execute_process(
    COMMAND "${CRIMSON_PYTHON_EXECUTABLE}" -c
            "import sys; print('{}.{}'.format(*sys.version_info[:2]))"
    OUTPUT_VARIABLE CRIMSON_PYTHON_VERSION
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

if(NOT CRIMSON_PYTHON_VERSION STREQUAL "2.7")
    message(FATAL_ERROR
        "CRIMSON controllers require Python 2.7; found ${CRIMSON_PYTHON_VERSION}")
endif()

# 3. Build the local CRIMSON Python runtime helper
# This target is part of the default build. It is not linked into the Python 3
# nanobind module.
add_library(
    crimson_python_runtime
    STATIC
    CrimsonPythonRuntime.cpp
)

target_include_directories(
    crimson_python_runtime
    PUBLIC
    "${CRIMSON_PYTHON_INCLUDE_DIR}"
    PRIVATE
    "${CRIMSON_DEPS}/boost_1_74/include"
)

target_compile_definitions(
    crimson_python_runtime
    PRIVATE
    CRIMSON_PYTHON_DEFAULT_HOME="${CRIMSON_PYTHON_ROOT}"
    CRIMSON_FLOWSOLVER_DEFAULT_HOME="${CRIMSON_ROOT}"
)

target_link_libraries(
    crimson_python_runtime
    PRIVATE
    "${CRIMSON_PYTHON_LIBRARY}"
    "${CRIMSON_DEPS}/boost_1_74/lib/libboost_filesystem.so"
    "${CRIMSON_DEPS}/boost_1_74/lib/libboost_system.so"
)

# 4. Include Directories
# (Needed so the compiler understands CRIMSON types in your Bridge code)
include_directories(
    ${CRIMSON_ROOT}/flowsolver/src
    ${CRIMSON_ROOT}/estimation/src
    ${CRIMSON_ROOT}/solverio/src
    ${CRIMSON_ROOT}/utils/src
    ${CRIMSON_ROOT}/common/src
    ${CRIMSON_ROOT}/gtest-1.7.0/include
    
    ${CRIMSON_DEPS}/petsc/include
    ${CRIMSON_DEPS}/boost_1_74/include
    ${CRIMSON_DEPS}/openblas/include
    ${CRIMSON_DEPS}/vtk-crimson/include/vtk-5.8
)

# 5. Build the standalone CRIMSON netlist worker.
# This executable owns the Python 2 controller runtime in a separate process;
# it must never be linked into STARFiSh's Python 3 nanobind module.
add_executable(
    crimson_netlist_worker
    CrimsonNetlistWorker.cpp
    CrimsonNetlistRuntime.cpp
    CrimsonControlSystems.cpp
)

target_compile_definitions(
    crimson_netlist_worker
    PRIVATE
    PETSC_USE_REAL_SCALAR
)

target_link_libraries(
    crimson_netlist_worker
    PRIVATE
    crimson_python_runtime

    # CRIMSON static libraries
    ${CRIMSON_LIB_DIR}/libcrimson_flowsolver.a
    ${CRIMSON_LIB_DIR}/libcrimson_solverio.a
    ${CRIMSON_LIB_DIR}/libcrimson_common.a

    # External dependencies
    ${CRIMSON_DEPS}/petsc/lib/libpetsc.so
    ${CRIMSON_DEPS}/petsc/lib/libmpicxx.so
    ${CRIMSON_DEPS}/petsc/lib/libmpi.so
    ${CRIMSON_DEPS}/openblas/lib/libopenblas.so
    ${CRIMSON_DEPS}/boost_1_74/lib/libboost_system.so
    ${CRIMSON_DEPS}/boost_1_74/lib/libboost_filesystem.so
    ${CRIMSON_DEPS}/boost_1_74/lib/libboost_thread.so
)

# 6. Build the Python module from your Bridge files ONLY
# We do NOT include .cxx files here because we link the .a libs instead
nanobind_add_module(crimson_starfish_bridge 
    bindings.cpp 
    StarfishBridge.cpp
)

# 7. Force the bridge to use Real scalars to match CRIMSON's core
target_compile_definitions(crimson_starfish_bridge PRIVATE PETSC_USE_REAL_SCALAR)

# 8. Link everything together
# We link the .a libraries which contain all the symbols (NetlistReader, etc.)
target_link_libraries(crimson_starfish_bridge PRIVATE 
    # CRIMSON Static Libraries (order can matter, specialized first)
    ${CRIMSON_LIB_DIR}/libcrimson_flowsolver.a
    ${CRIMSON_LIB_DIR}/libcrimson_solverio.a
    ${CRIMSON_LIB_DIR}/libcrimson_common.a
    
    # External Dependencies
    ${CRIMSON_DEPS}/petsc/lib/libpetsc.so
    ${CRIMSON_DEPS}/openblas/lib/libopenblas.so
    ${CRIMSON_DEPS}/boost_1_74/lib/libboost_system.so
    ${CRIMSON_DEPS}/boost_1_74/lib/libboost_filesystem.so
    ${CRIMSON_DEPS}/boost_1_74/lib/libboost_thread.so
)
