#include "CrimsonPythonRuntime.hxx"

#include <Python.h>

#include <exception>
#include <iostream>

int main()
{
    try {
        initialisePython();

        std::cout << "Python runtime: " << Py_GetVersion() << std::endl;
        std::cout << "CRIMSONPython import: OK" << std::endl;

        Py_Finalize();
        return 0;
    }
    catch (const std::exception& error) {
        if (PyErr_Occurred()) {
            PyErr_Print();
        }

        std::cerr << "Runtime check failed: "
                  << error.what()
                  << std::endl;
        return 1;
    }
}
