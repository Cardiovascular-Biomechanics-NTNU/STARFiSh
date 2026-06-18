#include "CrimsonControlSystems.hxx"
#include "CrimsonPythonRuntime.hxx"

#include "CircuitComponent.hxx"
#include "NetlistCircuit.hxx"
#include "NetlistXmlReader.hxx"

#include <petscsys.h>

#include <cmath>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <utility>
#include <vector>

#include <boost/filesystem.hpp>
#include <boost/shared_ptr.hpp>

#ifndef STARFISH_TEST_CONTROLLER_DIR
#define STARFISH_TEST_CONTROLLER_DIR "controllers"
#endif

int main()
{
    const boost::filesystem::path fixtureDirectory(
        STARFISH_TEST_CONTROLLER_DIR);

    try {
        if (!boost::filesystem::exists(
                fixtureDirectory / "netlist_surfaces.xml")) {
            throw std::runtime_error(
                "The controlled-resistance fixture was not found.");
        }

        boost::filesystem::current_path(fixtureDirectory);

        PetscBool petscInitialized;
        PetscInitialized(&petscInitialized);
        if (!petscInitialized) {
            PetscInitialize(NULL, NULL, NULL, NULL);
        }

        initialisePython();

        const int numberOfCircuits = 1;
        const int hstep = 10;
        const double alfi = 1.0;
        const double dt = 0.001;

        const int expectedControllers = 1;
        int actualControllers = 0;
        double resistanceBeforeUpdate = 0.0;
        double resistanceAfterUpdate = 0.0;
        std::pair<double, double> coefficientsBeforeUpdate;
        std::pair<double, double> coefficientsAfterUpdate;

        // Controllers must be destroyed before Py_Finalize(), and circuits
        // must be destroyed before PetscFinalize().
        {
            std::vector<double> pressures(numberOfCircuits, 0.0);
            std::vector<double> flows(numberOfCircuits, 0.0);
            std::vector<
                std::pair<int, boost::shared_ptr<NetlistCircuit> >
            > circuits;

            for (int netlistIndex = 0;
                 netlistIndex < numberOfCircuits;
                 ++netlistIndex) {
                const int surfaceId = netlistIndex + 1;
                boost::shared_ptr<NetlistCircuit> circuit(
                    new NetlistCircuit(
                        hstep,
                        surfaceId,
                        netlistIndex,
                        false,
                        alfi,
                        dt,
                        0));

                circuit->setNetlistXmlFileName("netlist_surfaces.xml");
                circuit->setPressureAndFlowPointers(
                    &pressures[netlistIndex],
                    &flows[netlistIndex]);
                circuit->createCircuitDescription();
                circuit->closeAllDiodes();
                circuit->detectWhetherClosedDiodesStopAllFlowAt3DInterface();
                circuit->initialiseCircuit();

                circuits.push_back(std::make_pair(netlistIndex, circuit));
            }

            CrimsonControlSystems controlSystems(dt, false, 0, 1000);
            controlSystems.initialize(circuits);
            actualControllers = controlSystems.controllerCount();
            if (actualControllers != expectedControllers) {
                throw std::runtime_error(
                    "Unexpected number of CRIMSON control systems.");
            }

            double* resistance =
                circuits[0].second
                    ->getComponentByInputDataIndex(1)
                    ->getParameterPointer();

            circuits[0].second->initialiseAtStartOfTimestep();
            coefficientsBeforeUpdate =
                circuits[0].second->computeImplicitCoefficients(
                    0,
                    dt,
                    alfi * dt);

            resistanceBeforeUpdate = *resistance;
            controlSystems.update();
            resistanceAfterUpdate = *resistance;

            circuits[0].second->initialiseAtStartOfTimestep();
            coefficientsAfterUpdate =
                circuits[0].second->computeImplicitCoefficients(
                    1,
                    2.0 * dt,
                    alfi * dt);

            if (std::fabs(resistanceBeforeUpdate - 100.0) > 1.0e-12 ||
                std::fabs(resistanceAfterUpdate - 200.0) > 1.0e-12) {
                throw std::runtime_error(
                    "The controlled resistance did not change from 100 to 200.");
            }
            if (std::fabs(coefficientsBeforeUpdate.first - 100.0) > 1.0e-12 ||
                std::fabs(coefficientsAfterUpdate.first - 200.0) > 1.0e-12 ||
                std::fabs(coefficientsBeforeUpdate.second) > 1.0e-12 ||
                std::fabs(coefficientsAfterUpdate.second) > 1.0e-12) {
                throw std::runtime_error(
                    "The controller update was not reflected in dp_dq and Hop.");
            }

            std::cout << "Netlist circuits:    " << numberOfCircuits << std::endl;
            std::cout << "Python controllers:  " << actualControllers << std::endl;
            std::cout << "Resistance before:   " << resistanceBeforeUpdate << std::endl;
            std::cout << "Resistance after:    " << resistanceAfterUpdate << std::endl;
            std::cout << "dp_dq before:        "
                      << coefficientsBeforeUpdate.first << std::endl;
            std::cout << "dp_dq after:         "
                      << coefficientsAfterUpdate.first << std::endl;
            std::cout << "Hop before/after:    "
                      << coefficientsBeforeUpdate.second << " / "
                      << coefficientsAfterUpdate.second << std::endl;
            std::cout << "CRIMSON controller numerical update: OK"
                      << std::endl;
        }

        NetlistXmlReader::Term();
        Py_Finalize();
        PetscFinalize();
        return 0;
    }
    catch (const std::exception& error) {
        if (Py_IsInitialized() && PyErr_Occurred()) {
            PyErr_Print();
        }
        std::cerr << "Control-system check failed: "
                  << error.what()
                  << std::endl;
        return 1;
    }
}
