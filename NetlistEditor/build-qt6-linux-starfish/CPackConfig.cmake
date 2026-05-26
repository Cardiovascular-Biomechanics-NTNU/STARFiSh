# This file will be configured to contain variables for CPack. These variables
# should be set in the CMake list file of the project before CPack module is
# included. The list of available CPACK_xxx variables and their associated
# documentation may be obtained using
#  cpack --help-variable-list
#
# Some variables are common to all generators (e.g. CPACK_PACKAGE_NAME)
# and some are specific to a generator
# (e.g. CPACK_NSIS_EXTRA_INSTALL_COMMANDS). The generator specific variables
# usually begin with CPACK_<GENNAME>_xxxx.


set(CPACK_BUILD_SOURCE_DIRS "/home/sadid/starfish/NetlistEditor;/home/sadid/starfish/NetlistEditor/build-qt6-linux-starfish")
set(CPACK_CMAKE_GENERATOR "Unix Makefiles")
set(CPACK_COMPONENT_UNSPECIFIED_HIDDEN "TRUE")
set(CPACK_COMPONENT_UNSPECIFIED_REQUIRED "TRUE")
set(CPACK_DEBIAN_PACKAGE_DEPENDS "libstdc++6 (>=4.3.2-1.1),
      libqt4-core (>=4.6),
      libqt4-gui (>=4.6),
      libqwt5-qt4 (>=5.0)")
set(CPACK_DEBIAN_PACKAGE_MAINTAINER "Michele Caini <michele.caini@gmail.com>")
set(CPACK_DEBIAN_PACKAGE_SECTION "Electronics")
set(CPACK_DEBIAN_PACKAGE_VERSION "+sid")
set(CPACK_DEFAULT_PACKAGE_DESCRIPTION_FILE "/usr/share/cmake-3.28/Templates/CPack.GenericDescription.txt")
set(CPACK_DEFAULT_PACKAGE_DESCRIPTION_SUMMARY "CRIMSONBCT built using CMake")
set(CPACK_DMG_SLA_USE_RESOURCE_FILE_LICENSE "ON")
set(CPACK_GENERATOR "TZ;TGZ;TBZ2;DEB")
set(CPACK_INNOSETUP_ARCHITECTURE "x64")
set(CPACK_INSTALL_CMAKE_PROJECTS "/home/sadid/starfish/NetlistEditor/build-qt6-linux-starfish;CRIMSON Boundary Condition Toolbox;ALL;/")
set(CPACK_INSTALL_PREFIX "/usr/local")
set(CPACK_MODULE_PATH "/home/sadid/starfish/NetlistEditor/cmake/Modules/")
set(CPACK_NSIS_DISPLAY_NAME "CRIMSON Boundary Condition Toolbox-0.1")
set(CPACK_NSIS_INSTALLER_ICON_CODE "")
set(CPACK_NSIS_INSTALLER_MUI_ICON_CODE "")
set(CPACK_NSIS_INSTALL_ROOT "$PROGRAMFILES")
set(CPACK_NSIS_PACKAGE_NAME "CRIMSON Boundary Condition Toolbox-0.1")
set(CPACK_NSIS_UNINSTALL_NAME "Uninstall")
set(CPACK_OBJCOPY_EXECUTABLE "/usr/bin/objcopy")
set(CPACK_OBJDUMP_EXECUTABLE "/usr/bin/objdump")
set(CPACK_OUTPUT_CONFIG_FILE "/home/sadid/starfish/NetlistEditor/build-qt6-linux-starfish/CPackConfig.cmake")
set(CPACK_PACKAGE_DEFAULT_LOCATION "/")
set(CPACK_PACKAGE_DESCRIPTION_FILE "/usr/share/cmake-3.28/Templates/CPack.GenericDescription.txt")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "QSapecNG - Qt-based GUI for SapecNG")
set(CPACK_PACKAGE_FILE_NAME "CRIMSON Boundary Condition Toolbox-0.1.0")
set(CPACK_PACKAGE_INSTALL_DIRECTORY "CRIMSON Boundary Condition Toolbox-0.1")
set(CPACK_PACKAGE_INSTALL_REGISTRY_KEY "CRIMSON Boundary Condition Toolbox-0.1")
set(CPACK_PACKAGE_NAME "CRIMSON Boundary Condition Toolbox")
set(CPACK_PACKAGE_RELOCATABLE "true")
set(CPACK_PACKAGE_VENDOR "Michele Caini <michele.caini@gmail.com>")
set(CPACK_PACKAGE_VERSION "0.1.0")
set(CPACK_PACKAGE_VERSION_MAJOR "0")
set(CPACK_PACKAGE_VERSION_MINOR "1")
set(CPACK_PACKAGE_VERSION_PATCH "0")
set(CPACK_READELF_EXECUTABLE "/usr/bin/readelf")
set(CPACK_RESOURCE_FILE_LICENSE "/home/sadid/starfish/NetlistEditor/LICENSE")
set(CPACK_RESOURCE_FILE_README "/home/sadid/starfish/NetlistEditor/README")
set(CPACK_RESOURCE_FILE_WELCOME "/usr/share/cmake-3.28/Templates/CPack.GenericWelcome.txt")
set(CPACK_SET_DESTDIR "OFF")
set(CPACK_SOURCE_GENERATOR "TBZ2;TGZ;ZIP")
set(CPACK_SOURCE_IGNORE_FILES ".*~;.*kdev*;/CMakeFiles/;/_CPack_Packages/;/\\.svn/;/\\.DS_Store;/\\.Trashes/;\\.cproject;\\.project;CMakeCache\\.txt;build.*;\\.settings;.*\\.patch;moc_qtbuttonpropertybrowser\\.cpp;moc_qteditorfactory\\.cpp;moc_qtgroupboxpropertybrowser\\.cpp;moc_qtpropertybrowser\\.cpp;moc_qtpropertybrowserutils_p\\.cpp;moc_qtpropertymanager\\.cpp;moc_qttreepropertybrowser\\.cpp;moc_qtvariantproperty\\.cpp;qteditorfactory\\.moc;qtpropertymanager\\.moc;qttreepropertybrowser\\.moc;/\\.pc/;/home/sadid/starfish/NetlistEditor/debian/")
set(CPACK_SOURCE_OUTPUT_CONFIG_FILE "/home/sadid/starfish/NetlistEditor/build-qt6-linux-starfish/CPackSourceConfig.cmake")
set(CPACK_SOURCE_PACKAGE_FILE_NAME "CRIMSON Boundary Condition Toolbox-0.1.0-source")
set(CPACK_SOURCE_STRIP_FILES "")
set(CPACK_STRIP_FILES "usr/bin/CRIMSONBCT")
set(CPACK_SYSTEM_NAME "Linux")
set(CPACK_THREADS "1")
set(CPACK_TOPLEVEL_TAG "Linux")
set(CPACK_WIX_SIZEOF_VOID_P "8")

if(NOT CPACK_PROPERTIES_FILE)
  set(CPACK_PROPERTIES_FILE "/home/sadid/starfish/NetlistEditor/build-qt6-linux-starfish/CPackProperties.cmake")
endif()

if(EXISTS ${CPACK_PROPERTIES_FILE})
  include(${CPACK_PROPERTIES_FILE})
endif()
