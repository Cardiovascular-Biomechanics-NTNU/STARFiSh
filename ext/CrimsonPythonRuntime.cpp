#include "CrimsonPythonRuntime.hxx"

#include <cstdlib>
#include <sstream>
#include <stdexcept>

#include <boost/filesystem.hpp>

#ifndef CRIMSON_PYTHON_DEFAULT_HOME
#define CRIMSON_PYTHON_DEFAULT_HOME ""
#endif

#ifndef CRIMSON_FLOWSOLVER_DEFAULT_HOME
#define CRIMSON_FLOWSOLVER_DEFAULT_HOME ""
#endif

void initialisePython()
{
    if (Py_IsInitialized()) {
        return;
    }

    const char* pythonHome = std::getenv("CRIMSON_PYTHON_HOME");
    if (pythonHome == NULL) {
        pythonHome = CRIMSON_PYTHON_DEFAULT_HOME;
    }
    if (pythonHome[0] == '\0') {
        throw std::runtime_error(
            "CRIMSON_PYTHON_HOME is not set and no build-time default is available.");
    }

    const boost::filesystem::path pythonHomePath(pythonHome);
    if (!boost::filesystem::exists(pythonHomePath / "bin" / "python")) {
        throw std::runtime_error("CRIMSON Python executable was not found.");
    }

    const char* crimsonHome = std::getenv("CRIMSON_FLOWSOLVER_HOME");
    if (crimsonHome == NULL) {
        crimsonHome = CRIMSON_FLOWSOLVER_DEFAULT_HOME;
    }
    if (crimsonHome[0] == '\0') {
        throw std::runtime_error(
            "CRIMSON_FLOWSOLVER_HOME is not set and no build-time default is available.");
    }

    boost::filesystem::path controllerLibrary(crimsonHome);
    controllerLibrary /= "basicControlScripts/lib";
    if (!boost::filesystem::exists(controllerLibrary)) {
        throw std::runtime_error("CRIMSON basicControlScripts/lib was not found.");
    }

    // Python 2 requires the home to be set before interpreter initialization.
    Py_SetPythonHome(const_cast<char*>(pythonHome));
    Py_Initialize();
    if (!Py_IsInitialized()) {
        throw std::runtime_error("Failed to initialize CRIMSON Python 2.7.");
    }

    PyRun_SimpleString("import sys");

    std::stringstream addControllerPath;
    addControllerPath << "sys.path.insert(0, r'"
                      << controllerLibrary.string()
                      << "')";
    if (PyRun_SimpleString(addControllerPath.str().c_str()) != 0) {
        throw std::runtime_error(
            "Failed to configure the CRIMSON controller import path.");
    }

    PyObject* crimsonPythonModule = PyImport_ImportModule("CRIMSONPython");
    if (crimsonPythonModule == NULL) {
        PyErr_Print();
        throw std::runtime_error(
            "Failed to import CRIMSONPython from basicControlScripts/lib.");
    }
    safe_Py_DECREF(crimsonPythonModule);
}

void safe_Py_DECREF(PyObject* object)
{
    if (object != NULL) {
        Py_DECREF(object);
    }
}
