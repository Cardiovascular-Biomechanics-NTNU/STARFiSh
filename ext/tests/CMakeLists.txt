cmake_minimum_required(VERSION 3.15)

set(CRIMSON_ROOT
    "/home/sadid/crimson/cfs_reg/CRIMSONFlowsolver"
    CACHE PATH
    "CRIMSONFlowsolver source root")
set(CRIMSON_DEPS
    "/home/sadid/crimson/deps/installs"
    CACHE PATH
    "CRIMSON dependency installation root")
set(CRIMSON_PYTHON_ROOT
    "/home/sadid/miniconda3/envs/flow"
    CACHE PATH
    "Python 2.7 environment used by CRIMSON controllers")

set(
    CMAKE_CXX_COMPILER
    "${CRIMSON_DEPS}/petsc/bin/mpicxx"
    CACHE FILEPATH
    "MPI C++ compiler used by CRIMSON PETSc"
    FORCE)

project(crimson_starfish_tests LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(STARFISH_EXT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/..")
set(CRIMSON_LIB_DIR "${CRIMSON_ROOT}/lib")
set(CRIMSON_PYTHON_INCLUDE_DIR
    "${CRIMSON_PYTHON_ROOT}/include/python2.7")
set(CRIMSON_PYTHON_LIBRARY_DIR
    "${CRIMSON_PYTHON_ROOT}/lib")

find_library(
    CRIMSON_PYTHON_LIBRARY
    NAMES python2.7
    PATHS "${CRIMSON_PYTHON_LIBRARY_DIR}"
    NO_DEFAULT_PATH
    REQUIRED)

set(CRIMSON_COMMON_INCLUDE_DIRS
    "${STARFISH_EXT_DIR}"
    "${CRIMSON_ROOT}/flowsolver/src"
    "${CRIMSON_ROOT}/estimation/src"
    "${CRIMSON_ROOT}/solverio/src"
    "${CRIMSON_ROOT}/utils/src"
    "${CRIMSON_ROOT}/common/src"
    "${CRIMSON_ROOT}/gtest-1.7.0/include"
    "${CRIMSON_DEPS}/petsc/include"
    "${CRIMSON_DEPS}/boost_1_74/include"
    "${CRIMSON_DEPS}/openblas/include")

set(CRIMSON_COMMON_LIBRARIES
    "${CRIMSON_LIB_DIR}/libcrimson_flowsolver.a"
    "${CRIMSON_LIB_DIR}/libcrimson_solverio.a"
    "${CRIMSON_LIB_DIR}/libcrimson_common.a"
    "${CRIMSON_DEPS}/petsc/lib/libpetsc.so"
    "${CRIMSON_DEPS}/openblas/lib/libopenblas.so"
    "${CRIMSON_DEPS}/boost_1_74/lib/libboost_system.so"
    "${CRIMSON_DEPS}/boost_1_74/lib/libboost_filesystem.so"
    "${CRIMSON_DEPS}/boost_1_74/lib/libboost_thread.so")

add_library(
    crimson_python_runtime_test_support
    STATIC
    "${STARFISH_EXT_DIR}/CrimsonPythonRuntime.cpp")

target_include_directories(
    crimson_python_runtime_test_support
    PUBLIC
    "${STARFISH_EXT_DIR}"
    "${CRIMSON_PYTHON_INCLUDE_DIR}"
    PRIVATE
    "${CRIMSON_DEPS}/boost_1_74/include")

target_compile_definitions(
    crimson_python_runtime_test_support
    PRIVATE
    CRIMSON_PYTHON_DEFAULT_HOME="${CRIMSON_PYTHON_ROOT}"
    CRIMSON_FLOWSOLVER_DEFAULT_HOME="${CRIMSON_ROOT}")

target_link_libraries(
    crimson_python_runtime_test_support
    PUBLIC
    "${CRIMSON_PYTHON_LIBRARY}"
    "${CRIMSON_DEPS}/boost_1_74/lib/libboost_filesystem.so"
    "${CRIMSON_DEPS}/boost_1_74/lib/libboost_system.so")

add_executable(
    crimson_python_runtime_check
    CrimsonPythonRuntimeCheck.cpp)
target_link_libraries(
    crimson_python_runtime_check
    PRIVATE
    crimson_python_runtime_test_support)

add_executable(
    crimson_controller_check
    CrimsonControllerCheck.cpp)
target_compile_definitions(
    crimson_controller_check
    PRIVATE
    STARFISH_TEST_CONTROLLER_DIR="${CMAKE_CURRENT_SOURCE_DIR}/controllers")
target_link_libraries(
    crimson_controller_check
    PRIVATE
    crimson_python_runtime_test_support)

add_executable(
    crimson_control_systems_check
    CrimsonControlSystemsCheck.cpp
    "${STARFISH_EXT_DIR}/CrimsonControlSystems.cpp")
target_include_directories(
    crimson_control_systems_check
    PRIVATE
    ${CRIMSON_COMMON_INCLUDE_DIRS})
target_compile_definitions(
    crimson_control_systems_check
    PRIVATE
    PETSC_USE_REAL_SCALAR
    STARFISH_TEST_CONTROLLER_DIR="${CMAKE_CURRENT_SOURCE_DIR}/controllers")
target_link_libraries(
    crimson_control_systems_check
    PRIVATE
    crimson_python_runtime_test_support
    ${CRIMSON_COMMON_LIBRARIES})

add_executable(
    crimson_netlist_runtime_check
    CrimsonNetlistRuntimeCheck.cpp
    "${STARFISH_EXT_DIR}/CrimsonNetlistRuntime.cpp"
    "${STARFISH_EXT_DIR}/CrimsonControlSystems.cpp")
target_include_directories(
    crimson_netlist_runtime_check
    PRIVATE
    ${CRIMSON_COMMON_INCLUDE_DIRS})
target_compile_definitions(
    crimson_netlist_runtime_check
    PRIVATE
    PETSC_USE_REAL_SCALAR
    STARFISH_TEST_PASSIVE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/passive")
target_link_libraries(
    crimson_netlist_runtime_check
    PRIVATE
    crimson_python_runtime_test_support
    ${CRIMSON_COMMON_LIBRARIES})

add_executable(
    crimson_netlist_controlled_runtime_check
    CrimsonNetlistControlledRuntimeCheck.cpp
    "${STARFISH_EXT_DIR}/CrimsonNetlistRuntime.cpp"
    "${STARFISH_EXT_DIR}/CrimsonControlSystems.cpp")
target_include_directories(
    crimson_netlist_controlled_runtime_check
    PRIVATE
    ${CRIMSON_COMMON_INCLUDE_DIRS})
target_compile_definitions(
    crimson_netlist_controlled_runtime_check
    PRIVATE
    PETSC_USE_REAL_SCALAR
    STARFISH_TEST_CONTROLLER_DIR="${CMAKE_CURRENT_SOURCE_DIR}/controllers")
target_link_libraries(
    crimson_netlist_controlled_runtime_check
    PRIVATE
    crimson_python_runtime_test_support
    ${CRIMSON_COMMON_LIBRARIES})

enable_testing()
add_test(
    NAME crimson_python_runtime_check
    COMMAND crimson_python_runtime_check)
add_test(
    NAME crimson_controller_check
    COMMAND crimson_controller_check)
add_test(
    NAME crimson_control_systems_check
    COMMAND crimson_control_systems_check)
add_test(
    NAME crimson_netlist_runtime_check
    COMMAND crimson_netlist_runtime_check)
add_test(
    NAME crimson_netlist_controlled_runtime_check
    COMMAND crimson_netlist_controlled_runtime_check)
