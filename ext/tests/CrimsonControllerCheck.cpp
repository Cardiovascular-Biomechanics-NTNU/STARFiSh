#include "CrimsonPythonRuntime.hxx"

#include <Python.h>

#include <cmath>
#include <exception>
#include <iostream>
#include <stdexcept>

namespace {

#ifndef STARFISH_TEST_CONTROLLER_DIR
#define STARFISH_TEST_CONTROLLER_DIR "controllers"
#endif

void requireObject(PyObject* object, const char* errorMessage)
{
    if (object == NULL) {
        PyErr_Print();
        throw std::runtime_error(errorMessage);
    }
}

} // namespace

int main()
{
    try {
        initialisePython();

        PyObject* sysPath = PySys_GetObject(const_cast<char*>("path"));
        requireObject(sysPath, "Failed to access Python sys.path.");
        PyObject* fixturePath = PyString_FromString(
            STARFISH_TEST_CONTROLLER_DIR);
        requireObject(fixturePath, "Failed to create the controller fixture path.");
        if (PyList_Insert(sysPath, 0, fixturePath) != 0) {
            safe_Py_DECREF(fixturePath);
            throw std::runtime_error("Failed to add the controller fixture path.");
        }
        safe_Py_DECREF(fixturePath);

        PyObject* module = PyImport_ImportModule("constantResistanceController");
        requireObject(module, "Failed to import constantResistanceController.");

        PyObject* controllerClass = PyObject_GetAttrString(module, "parameterController");
        requireObject(controllerClass, "Failed to find parameterController.");

        PyObject* controller = PyObject_CallFunction(
            controllerClass,
            const_cast<char*>("si"),
            "controllerCheck",
            0);
        requireObject(controller, "Failed to instantiate parameterController.");

        PyObject* qualificationResult =
            PyObject_CallMethod(
                controller,
                const_cast<char*>("recieveExtraData"),
                const_cast<char*>("s"),
                "_component_1");
        requireObject(qualificationResult, "Failed to pass controller qualification data.");
        safe_Py_DECREF(qualificationResult);

        PyObject* pressures = PyDict_New();
        PyObject* flows = PyDict_New();
        PyObject* volumes = PyDict_New();
        requireObject(pressures, "Failed to create pressure dictionary.");
        requireObject(flows, "Failed to create flow dictionary.");
        requireObject(volumes, "Failed to create volume dictionary.");

        const double initialResistance = 100.0;
        PyObject* updatedResistance = PyObject_CallMethod(
            controller,
            const_cast<char*>("updateControl"),
            const_cast<char*>("ddOOO"),
            initialResistance,
            0.01,
            pressures,
            flows,
            volumes);
        requireObject(updatedResistance, "Failed to call updateControl.");

        const double result = PyFloat_AsDouble(updatedResistance);
        if (PyErr_Occurred()) {
            PyErr_Print();
            throw std::runtime_error("Controller did not return a numeric parameter.");
        }
        if (std::fabs(result - 200.0) > 1.0e-12) {
            throw std::runtime_error("Controller returned an unexpected parameter value.");
        }

        std::cout << "Controller input:  " << initialResistance << std::endl;
        std::cout << "Controller output: " << result << std::endl;
        std::cout << "CRIMSON controller call: OK" << std::endl;

        safe_Py_DECREF(updatedResistance);
        safe_Py_DECREF(volumes);
        safe_Py_DECREF(flows);
        safe_Py_DECREF(pressures);
        safe_Py_DECREF(controller);
        safe_Py_DECREF(controllerClass);
        safe_Py_DECREF(module);

        Py_Finalize();
        return 0;
    }
    catch (const std::exception& error) {
        if (PyErr_Occurred()) {
            PyErr_Print();
        }
        std::cerr << "Controller check failed: " << error.what() << std::endl;
        return 1;
    }
}
