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

#ifndef STARFISH_TEST_PASSIVE_DIR
#define STARFISH_TEST_PASSIVE_DIR "passive"
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
                  "starfish-netlist-runtime-%%%%-%%%%"))
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
            std::string("Unexpected passive runtime value for ") + quantity);
    }
}

void requireFile(
    const boost::filesystem::path& directory,
    const std::string& filename)
{
    if (!boost::filesystem::exists(directory / filename)) {
        throw std::runtime_error(
            "CRIMSON runtime did not create " + filename);
    }
}

} // namespace

int main()
{
    const boost::filesystem::path fixtureDirectory =
        boost::filesystem::absolute(STARFISH_TEST_PASSIVE_DIR);
    const boost::filesystem::path netlistXml =
        fixtureDirectory / "netlist_surfaces.xml";

    try {
        if (!boost::filesystem::exists(netlistXml)) {
            throw std::runtime_error(
                "The passive-resistance netlist fixture was not found.");
        }

        const int surfaceId = 1;
        const int timestep = 0;
        const int hstep = 10;
        const int startingTimestep = 0;
        const int restartInterval = 1000;
        const double alfi = 1.0;
        const double dt = 0.001;
        const double time = dt;
        const double flow = 1.0e-5;
        const double expectedResistance = 100.0;
        const double expectedHop = 0.0;
        const double pressure = expectedResistance * flow;

        TemporaryDirectory outputDirectory;
        std::pair<double, double> coefficients;
        int controllers = -1;

        PetscBool petscInitialized;
        PetscInitialized(&petscInitialized);
        if (!petscInitialized) {
            PetscInitialize(NULL, NULL, NULL, NULL);
        }
        initialisePython();

        // Runtime and its NetlistCircuit objects must be destroyed before the
        // XML singleton, Python interpreter, and PETSc are finalized.
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
            runtime.startTimestep(timestep, time);

            coefficients = runtime.computeCoefficients(
                surfaceId,
                timestep,
                time,
                flow);

            requireNear(
                coefficients.first,
                expectedResistance,
                1.0e-12,
                "dp_dq");
            requireNear(
                coefficients.second,
                expectedHop,
                1.0e-12,
                "Hop");

            controllers = runtime.controllerCount();
            if (controllers != 0) {
                throw std::runtime_error(
                    "The passive runtime unexpectedly created controllers.");
            }

            runtime.updateState(
                surfaceId,
                timestep,
                pressure,
                flow);
            runtime.finalizeTimestep(timestep);
            runtime.flush();
        }

        requireFile(
            outputDirectory.path(),
            "netlistFlows_surface_1.dat");
        requireFile(
            outputDirectory.path(),
            "netlistPressures_surface_1.dat");
        requireFile(
            outputDirectory.path(),
            "netlistVolumes_surface_1.dat");

        NetlistXmlReader::Term();
        Py_Finalize();

        PetscInitialized(&petscInitialized);
        if (petscInitialized) {
            PetscFinalize();
        }

        std::cout << "Surface:             " << surfaceId << std::endl;
        std::cout << "Flow:                " << flow << std::endl;
        std::cout << "dp_dq:               " << coefficients.first << std::endl;
        std::cout << "Hop:                 " << coefficients.second << std::endl;
        std::cout << "Python controllers:  " << controllers << std::endl;
        std::cout << "CRIMSON passive runtime lifecycle: OK" << std::endl;
        return 0;
    }
    catch (const std::exception& error) {
        if (Py_IsInitialized() && PyErr_Occurred()) {
            PyErr_Print();
        }
        std::cerr << "Passive runtime check failed: "
                  << error.what()
                  << std::endl;
        return 1;
    }
}
