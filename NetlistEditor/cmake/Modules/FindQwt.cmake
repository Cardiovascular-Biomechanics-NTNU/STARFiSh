# Find Qwt for the NetlistEditor standalone build.
#
# Exports:
#   Qwt_FOUND
#   Qwt_INCLUDE_DIRS
#   Qwt_LIBRARIES

if(NETLISTEDITOR_USE_QT6)
  set(_QWT_LIBRARY_NAMES qwt qwt-qt6)
else()
  set(_QWT_LIBRARY_NAMES qwt-qt5 qwt)
endif()

find_path(Qwt_INCLUDE_DIR
  NAMES qwt_plot.h
  HINTS
    ${Qwt_ROOT}
    $ENV{QWT_ROOT}
    ${CMAKE_PREFIX_PATH}
  PATH_SUFFIXES
    include
    include/qwt
  PATHS
    /usr/local/qwt-6.3.0/include
    /usr/include/qwt
    /usr/local/include/qwt
)

find_library(Qwt_LIBRARY
  NAMES ${_QWT_LIBRARY_NAMES}
  HINTS
    ${Qwt_ROOT}
    $ENV{QWT_ROOT}
    ${CMAKE_PREFIX_PATH}
  PATH_SUFFIXES
    lib
  PATHS
    /usr/local/qwt-6.3.0/lib
    /usr/lib
    /usr/local/lib
    /usr/lib/x86_64-linux-gnu
)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(Qwt
  REQUIRED_VARS Qwt_INCLUDE_DIR Qwt_LIBRARY
)

if(Qwt_FOUND)
  set(Qwt_INCLUDE_DIRS "${Qwt_INCLUDE_DIR}")
  set(Qwt_LIBRARIES "${Qwt_LIBRARY}")
endif()

mark_as_advanced(Qwt_INCLUDE_DIR Qwt_LIBRARY)
unset(_QWT_LIBRARY_NAMES)
