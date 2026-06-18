// similar script to crimson/estimation/src/CRIMSONPython.hxx 

#ifndef STARFISH_CRIMSON_PYTHON_RUNTIME_HXX
#define STARFISH_CRIMSON_PYTHON_RUNTIME_HXX

#include <Python.h>

// Initialize the isolated Python 2.7 interpreter and add CRIMSON's
// basicControlScripts/lib directory to Python's import path.
void initialisePython();

// Safely release a Python object reference.
void safe_Py_DECREF(PyObject* object);

#endif