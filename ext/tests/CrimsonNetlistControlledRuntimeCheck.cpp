#include "CrimsonNetlistRuntime.hxx"
#include "CrimsonPythonRuntime.hxx"

#include "NetlistXmlReader.hxx"

#include <petscsys.h>

#include <boost/filesystem.hpp>

#include <cmath>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifndef STARFISH_TEST_CONTROLLER_DIR
#define STARFISH_TEST_CONTROLLER_DIR "controllers"
#endif

namespace
{

class TemporaryDirectory
{
public:
    TemporaryDirectory()
        : path_(
              boost::filesystem::temp_directory_path() /
              boost::filesystem::unique_path(
                  "starfish-controlled-runtime-%%%%-%%%%"))
    {
        boost::filesystem::create_directories(path_);
    }

    ~TemporaryDirectory()
    {
        boost::system::error_code error;
        boost::filesystem::remove_all(path_, error);
    }

    const boost::filesystem::path& path() const
    {
        return path_;
    }

private:
    boost::filesystem::path path_;
};

void requireNear(
    double actual,
    double expected,
    double tolerance,
    const char* quantity)
{
    if (std::fabs(actual - expected) > tolerance) {
        throw std::runtime_error(
            std::string("Unexpected controlled runtime value for ") + quantity);
    }
}

} // namespace

int main()
{
    const boost::filesystem::path fixtureDirectory =
        boost::filesystem::absolute(STARFISH_TEST_CONTROLLER_DIR);
    const boost::filesystem::path netlistXml =
        fixtureDirectory / "netlist_surfaces.xml";

    try {
        if (!boost::filesystem::exists(netlistXml)) {
            throw std::runtime_error(
                "The controlled-resistance netlist fixture was not found.");
        }

        const int surfaceId = 1;
        const int hstep = 10;
        const int startingTimestep = 0;
        const int restartInterval = 1000;
        const double alfi = 1.0;
        const double dt = 0.001;
        const double flow = 1.0e-5;
        const double resistanceAtTimestep0 = 100.0;
        const double resistanceAtTimestep1 = 200.0;

        TemporaryDirectory outputDirectory;
        std::pair<double, double> coefficientsAtTimestep0;
        std::pair<double, double> coefficientsAtTimestep1;
        int controllers = -1;

        PetscBool petscInitialized;
        PetscInitialized(&petscInitialized);
        if (!petscInitialized) {
            PetscInitialize(NULL, NULL, NULL, NULL);
        }
        initialisePython();

        // Runtime and controller objects must be destroyed before Python and
        // PETSc are finalized because CRIMSON controllers own Python objects.
        {
            CrimsonNetlistRuntime runtime(
                hstep,
                alfi,
                dt,
                startingTimestep,
                restartInterval,
                false);

            runtime.setOutputDirectory(outputDirectory.path().string());
            runtime.load(netlistXml.string(), std::vector<int>(1, surfaceId));

            controllers = runtime.controllerCount();
            if (controllers != 1) {
                throw std::runtime_error(
                    "The controlled runtime did not create one controller.");
            }

            runtime.startTimestep(0, dt);
            coefficientsAtTimestep0 = runtime.computeCoefficients(
                surfaceId,
                0,
                dt,
                flow);

            requireNear(
                coefficientsAtTimestep0.first,
                resistanceAtTimestep0,
                1.0e-12,
                "timestep-0 dp_dq");
            requireNear(
                coefficientsAtTimestep0.second,
                0.0,
                1.0e-12,
                "timestep-0 Hop");

            runtime.updateState(
                surfaceId,
                0,
                resistanceAtTimestep0 * flow,
                flow);
            runtime.finalizeTimestep(0);

            // finalizeTimestep(0) runs the Python controller. The updated
            // resistance must therefore affect the next boundary law.
            runtime.startTimestep(1, 2.0 * dt);
            coefficientsAtTimestep1 = runtime.computeCoefficients(
                surfaceId,
                1,
                2.0 * dt,
                flow);

            requireNear(
                coefficientsAtTimestep1.first,
                resistanceAtTimestep1,
                1.0e-12,
                "timestep-1 dp_dq");
            requireNear(
                coefficientsAtTimestep1.second,
                0.0,
                1.0e-12,
                "timestep-1 Hop");

            runtime.updateState(
                surfaceId,
                1,
                resistanceAtTimestep1 * flow,
                flow);
            runtime.finalizeTimestep(1);
        }

        NetlistXmlReader::Term();
        Py_Finalize();

        PetscInitialized(&petscInitialized);
        if (petscInitialized) {
            PetscFinalize();
        }

        std::cout << "Python controllers:  " << controllers << std::endl;
        std::cout << "dp_dq timestep 0:    "
                  << coefficientsAtTimestep0.first
                  << std::endl;
        std::cout << "dp_dq timestep 1:    "
                  << coefficientsAtTimestep1.first
                  << std::endl;
        std::cout << "Hop timestep 0/1:    "
                  << coefficientsAtTimestep0.second
                  << " / "
                  << coefficientsAtTimestep1.second
                  << std::endl;
        std::cout << "CRIMSON controlled runtime lifecycle: OK"
                  << std::endl;
        return 0;
    }
    catch (const std::exception& error) {
        if (Py_IsInitialized() && PyErr_Occurred()) {
            PyErr_Print();
        }
        std::cerr << "Controlled runtime check failed: "
                  << error.what()
                  << std::endl;
        return 1;
    }
}
