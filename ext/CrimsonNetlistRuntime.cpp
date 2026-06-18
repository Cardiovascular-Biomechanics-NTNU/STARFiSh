#include "CrimsonNetlistRuntime.hxx"

#include "CrimsonControlSystems.hxx"
#include "NetlistCircuit.hxx"

#include <algorithm>
#include <limits>
#include <stdexcept>

#include <boost/filesystem.hpp>

#include <petscsys.h>

CrimsonNetlistRuntime::SurfaceState::SurfaceState()
    : pressure(0.0),
      flow(0.0),
      netlistIndex(-1),
      nextTimestepWriteStart(0)
{
}

CrimsonNetlistRuntime::CrimsonNetlistRuntime(
    int hstep,
    double alfi,
    double dt,
    int startingTimestep,
    int restartInterval,
    bool masterControlScriptPresent)
    : hstep_(hstep),
      alfi_(alfi),
      dt_(dt),
      startingTimestep_(startingTimestep),
      restartInterval_(restartInterval),
      masterControlScriptPresent_(masterControlScriptPresent),
      loaded_(false),
      timestepStarted_(false),
      timestepFinalized_(false),
      currentTimestep_(-1)
{
    PetscBool petscInitialized;
    PetscInitialized(&petscInitialized);
    if (!petscInitialized) {
        PetscInitialize(NULL, NULL, NULL, NULL);
    }
}

void CrimsonNetlistRuntime::load(
    const std::string& netlistXml,
    const std::vector<int>& surfaceIds)
{
    if (loaded_) {
        throw std::runtime_error(
            "CrimsonNetlistRuntime::load() may only be called once.");
    }

    const boost::filesystem::path xmlPath(
        boost::filesystem::absolute(netlistXml));
    if (!boost::filesystem::exists(xmlPath)) {
        throw std::runtime_error(
            "CRIMSON netlist XML file was not found: " + xmlPath.string());
    }

    netlistXml_ = xmlPath.string();

    // XML circuits are indexed by their order in the file. Sorting makes the
    // STARFiSh surface-to-CRIMSON-circuit mapping reproducible.
    std::vector<int> sortedSurfaceIds = surfaceIds;
    std::sort(sortedSurfaceIds.begin(), sortedSurfaceIds.end());
    sortedSurfaceIds.erase(
        std::unique(sortedSurfaceIds.begin(), sortedSurfaceIds.end()),
        sortedSurfaceIds.end());

    // NetlistXmlReader still resolves netlist_surfaces.xml relative to the
    // process working directory. Limit that legacy requirement to loading.
    const boost::filesystem::path previousDirectory =
        boost::filesystem::current_path();
    try {
        boost::filesystem::current_path(xmlPath.parent_path());

        for (std::vector<int>::const_iterator surfaceId =
                 sortedSurfaceIds.begin();
             surfaceId != sortedSurfaceIds.end();
             ++surfaceId) {
            createSurface(
                *surfaceId,
                static_cast<int>(surfaces_.size()));
        }

        // Controller source names in netlist_surfaces.xml are resolved relative
        // to the case directory, so registration belongs inside the same
        // temporary working-directory scope as circuit creation.
        initializeControlSystems();
    }
    catch (...) {
        boost::filesystem::current_path(previousDirectory);
        throw;
    }
    boost::filesystem::current_path(previousDirectory);

    loaded_ = true;
}

void CrimsonNetlistRuntime::setOutputDirectory(
    const std::string& outputDirectory)
{
    outputDirectory_ = outputDirectory;
}

void CrimsonNetlistRuntime::startTimestep(
    int timestep,
    double /*time*/)
{
    requireLoaded();

    if (timestepStarted_ &&
        currentTimestep_ == timestep &&
        !timestepFinalized_) {
        return;
    }

    for (std::map<int, SurfaceState>::iterator surface = surfaces_.begin();
         surface != surfaces_.end();
         ++surface) {
        surface->second.circuit->initialiseAtStartOfTimestep();
    }

    currentTimestep_ = timestep;
    timestepStarted_ = true;
    timestepFinalized_ = false;
}

std::pair<double, double> CrimsonNetlistRuntime::computeCoefficients(
    int surfaceId,
    int timestep,
    double time,
    double flow)
{
    requireLoaded();
    startTimestep(timestep, time);

    SurfaceState& surface = getSurface(surfaceId);
    if (!surface.circuit->flowPermittedAcross3DInterface()) {
        // A non-leaky closed diode switches the interface to prescribed
        // zero-flow mode, so no Robin pressure law is available.
        return std::make_pair(
            std::numeric_limits<double>::quiet_NaN(),
            std::numeric_limits<double>::quiet_NaN());
    }

    surface.flow = flow;
    return surface.circuit->computeImplicitCoefficients(
        timestep,
        time,
        alfi_ * dt_);
}

std::pair<double, double> CrimsonNetlistRuntime::computeUpdateCoefficients(
    int surfaceId,
    int timestep,
    double time,
    double flow)
{
    requireLoaded();
    startTimestep(timestep, time);

    SurfaceState& surface = getSurface(surfaceId);
    if (!surface.circuit->flowPermittedAcross3DInterface()) {
        return std::make_pair(
            std::numeric_limits<double>::quiet_NaN(),
            std::numeric_limits<double>::quiet_NaN());
    }

    surface.flow = flow;
    // CRIMSON's corrector/update path intentionally uses dt rather than
    // alpha_f*dt.
    return surface.circuit->computeImplicitCoefficients(
        timestep,
        time,
        dt_);
}

bool CrimsonNetlistRuntime::flowPermitted(int surfaceId)
{
    requireLoaded();
    return getSurface(surfaceId)
        .circuit
        ->flowPermittedAcross3DInterface();
}

bool CrimsonNetlistRuntime::boundaryConditionTypeChanged(int surfaceId)
{
    requireLoaded();
    return getSurface(surfaceId)
        .circuit
        ->boundaryConditionTypeHasJustChanged();
}

void CrimsonNetlistRuntime::updateState(
    int surfaceId,
    int timestep,
    double pressure,
    double flow)
{
    requireLoaded();
    startTimestep(timestep, 0.0);

    SurfaceState& surface = getSurface(surfaceId);
    surface.pressure = pressure;
    surface.flow = flow;
    surface.circuit->updateLPN(timestep);
}

void CrimsonNetlistRuntime::finalizeTimestep(int timestep)
{
    requireLoaded();

    if (timestepFinalized_ && currentTimestep_ == timestep) {
        return;
    }
    if (!timestepStarted_ || currentTimestep_ != timestep) {
        throw std::runtime_error(
            "Cannot finalize a CRIMSON netlist timestep that was not started.");
    }

    for (std::map<int, SurfaceState>::iterator surface = surfaces_.begin();
         surface != surfaces_.end();
         ++surface) {
        surface->second.circuit->finalizeLPNAtEndOfTimestep();
    }

    // CRIMSON writers use relative filenames. Temporarily write from the
    // requested solution directory, then restore the caller's directory.
    const boost::filesystem::path previousDirectory =
        boost::filesystem::current_path();
    try {
        if (!outputDirectory_.empty()) {
            boost::filesystem::current_path(outputDirectory_);
        }

        for (std::map<int, SurfaceState>::iterator surface = surfaces_.begin();
             surface != surfaces_.end();
             ++surface) {
            surface->second.circuit->writePressuresFlowsAndVolumes(
                surface->second.nextTimestepWriteStart);
        }
    }
    catch (...) {
        boost::filesystem::current_path(previousDirectory);
        throw;
    }
    boost::filesystem::current_path(previousDirectory);

    // Match CRIMSON's end-of-timestep lifecycle: first commit and write the
    // converged circuit state, then let controllers modify parameters for the
    // next timestep's coefficient calculation.
    controlSystems_->update();

    timestepFinalized_ = true;
}

int CrimsonNetlistRuntime::controllerCount() const
{
    if (!controlSystems_) {
        return 0;
    }
    return controlSystems_->controllerCount();
}

CrimsonNetlistRuntime::SurfaceState&
CrimsonNetlistRuntime::getSurface(int surfaceId)
{
    std::map<int, SurfaceState>::iterator surface = surfaces_.find(surfaceId);
    if (surface == surfaces_.end()) {
        throw std::runtime_error(
            "No CRIMSON netlist circuit is registered for the requested surface.");
    }
    return surface->second;
}

void CrimsonNetlistRuntime::createSurface(
    int surfaceId,
    int netlistIndex)
{
    std::pair<std::map<int, SurfaceState>::iterator, bool> insertion =
        surfaces_.insert(std::make_pair(surfaceId, SurfaceState()));
    if (!insertion.second) {
        throw std::runtime_error(
            "Duplicate CRIMSON netlist surface id.");
    }

    SurfaceState& surface = insertion.first->second;
    surface.netlistIndex = netlistIndex;
    surface.nextTimestepWriteStart = startingTimestep_;
    surface.circuit = boost::shared_ptr<NetlistCircuit>(
        new NetlistCircuit(
            hstep_,
            surfaceId,
            netlistIndex,
            startingTimestep_ > 0,
            alfi_,
            dt_,
            startingTimestep_));

    // These addresses remain valid because std::map nodes are stable after
    // insertion. NetlistCircuit reads the latest values through these pointers.
    surface.circuit->setNetlistXmlFileName(netlistXml_);
    surface.circuit->setPressureAndFlowPointers(
        &surface.pressure,
        &surface.flow);
    surface.circuit->createCircuitDescription();
    surface.circuit->closeAllDiodes();
    surface.circuit->detectWhetherClosedDiodesStopAllFlowAt3DInterface();
    surface.circuit->initialiseCircuit();
}

void CrimsonNetlistRuntime::initializeControlSystems()
{
    std::vector<
        std::pair<int, boost::shared_ptr<NetlistCircuit> >
    > circuits;
    circuits.reserve(surfaces_.size());

    for (std::map<int, SurfaceState>::const_iterator surface = surfaces_.begin();
         surface != surfaces_.end();
         ++surface) {
        circuits.push_back(std::make_pair(
            surface->second.netlistIndex,
            surface->second.circuit));
    }

    controlSystems_ = boost::shared_ptr<CrimsonControlSystems>(
        new CrimsonControlSystems(
            dt_,
            masterControlScriptPresent_,
            startingTimestep_,
            restartInterval_));
    controlSystems_->initialize(circuits);
}

void CrimsonNetlistRuntime::requireLoaded() const
{
    if (!loaded_) {
        throw std::runtime_error(
            "CrimsonNetlistRuntime::load() must be called first.");
    }
}
