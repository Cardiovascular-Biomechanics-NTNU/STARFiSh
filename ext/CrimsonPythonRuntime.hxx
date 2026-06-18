#ifndef STARFISH_CRIMSON_PYTHON_RUNTIME_HXX
#define STARFISH_CRIMSON_PYTHON_RUNTIME_HXX

#include <Python.h>

/**
 * Initialize the isolated Python 2.7 interpreter used by CRIMSON controllers.
 *
 * The implementation uses environment overrides or CMake-provided defaults,
 * adds basicControlScripts/lib to sys.path, and verifies CRIMSONPython imports.
 */
void initialisePython();

// Match the helper symbol expected by CRIMSON's controller implementation.
void safe_Py_DECREF(PyObject* object);

#endif
