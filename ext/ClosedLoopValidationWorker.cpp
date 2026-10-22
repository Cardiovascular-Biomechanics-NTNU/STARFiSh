// Validation-only native CRIMSON subsection. The existing worker is preserved.
// No generated 0D replacement: Starfish supplies the external port inputs.
#include "ClosedLoopDownstreamSubsection.hxx"
#include "NetlistBoundaryCircuitWhenDownstreamCircuitsExist.hxx"
#include "NetlistXmlReader.hxx"
#include "ControlSystemsManager.hxx"
#include "CrimsonPythonRuntime.hxx"
#include <boost/filesystem.hpp>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

// Same upstream-then-downstream registration as BCM::createControlSystems.
// One native manager supplies priority ordering and cross-owner broadcasts.
void registerControls(ControlSystemsManager& manager, NetlistXmlReader* reader,
                      int index, const boost::shared_ptr<NetlistCircuit>& circuit) {
    const auto components = reader->getMapsOfComponentControlTypesForEachSurface();
    const auto nodes = reader->getMapsOfNodalControlTypesForEachSurface();
    const auto foundComponents = components.find(index);
    if (foundComponents != components.end()) {
        for (const auto& entry : foundComponents->second) {
            for (int k = 0; k < entry.second.getNumberOfControlScripts(); ++k)
                manager.createParameterController(entry.second.getControlTypeByIndexLocalToComponent(k),
                                                  circuit, entry.first);
        }
    }
    const auto foundNodes = nodes.find(index);
    if (foundNodes != nodes.end()) {
        for (const auto& entry : foundNodes->second)
            manager.createParameterController(entry.second, circuit, entry.first);
    }
}

void snapshot(const std::vector<boost::shared_ptr<NetlistCircuit>>& circuits,
              const boost::shared_ptr<ClosedLoopDownstreamSubsection>& downstream) {
    auto owners = circuits;
    owners.push_back(downstream->getNetlistCircuit());
    std::cout << "STARFISH_OK SNAPSHOT";
    for (const auto& circuit : owners) {
        const auto p = circuit->getNodeInputDataIndicesAndPressures();
        const auto q = circuit->getComponentInputDataIndicesAndFlows();
        const auto v = circuit->getVolumeTrackingComponentInputDataIndicesAndVolumes();
        for (const auto& values : {p, q, v}) {
            std::cout << ' ' << values.size();
            for (const auto& entry : values) std::cout << ' ' << *entry.second;
        }
    }
    std::cout << std::endl;
}
}

int main() {
    PetscInitialize(nullptr, nullptr, nullptr, nullptr);
    initialisePython();
    int status = 0;
    {
        boost::shared_ptr<ClosedLoopDownstreamSubsection> downstream;
        std::vector<boost::shared_ptr<NetlistCircuit>> circuits;
        std::vector<bool> connected;
        boost::shared_ptr<ControlSystemsManager> controls;
        std::vector<double> pressures, flows;
        int active = -1, accepted = -1;
        double dt = 0;
        bool trial = false;
        std::cout << std::setprecision(17) << "STARFISH_READY" << std::endl;
        std::string line;
        while (std::getline(std::cin, line)) {
            try {
                std::istringstream input(line);
                std::string command;
                input >> command;
                if (command == "QUIT") {
                    std::cout << "STARFISH_OK" << std::endl;
                    break;
                }
                if (command == "LOAD") {
                    require(!downstream, "LOAD can only be called once");
                    std::string directory;
                    int count;
                    input >> std::quoted(directory) >> dt >> count;
                    require(bool(input) && dt > 0 && std::isfinite(dt) && count > 0,
                            "LOAD requires directory, positive dt and port count");
                    boost::filesystem::current_path(directory);
                    // The adapter normalized physical IDs to 1..N in this snapshot.
                    downstream.reset(new ClosedLoopDownstreamSubsection(1, 1, dt, 1.0, 0));
                    pressures.assign(count, 0.0);
                    flows.assign(count, 0.0);
                    std::vector<boost::weak_ptr<ClosedLoopDownstreamSubsection>> links{downstream};
                    for (int i = 0; i < count; ++i) {
                        connected.push_back(downstream->boundaryConditionCircuitConnectsToThisDownstreamSubsection(i + 1));
                        boost::shared_ptr<NetlistCircuit> circuit;
                        if (connected.back()) circuit.reset(new NetlistBoundaryCircuitWhenDownstreamCircuitsExist(
                                1, i + 1, i, false, 1.0, dt, links, 0));
                        else circuit.reset(new NetlistCircuit(1, i + 1, i, false, 1.0, dt, 0));
                        circuit->setPressureAndFlowPointers(&pressures[i], &flows[i]);
                        circuit->createCircuitDescription();
                        circuit->closeAllDiodes();
                        circuit->detectWhetherClosedDiodesStopAllFlowAt3DInterface();
                        circuit->initialiseCircuit();
                        if (connected.back()) downstream->setPointerToNeighbouringBoundaryConditionCircuit(circuit);
                        circuits.push_back(circuit);
                    }
                    // Native fresh-run initialization sets a one-shot RHS flag
                    // that uses stored (zero) component flow on its first solve.
                    // Consume that explicit bootstrap before arbitrary external
                    // probes. No physical state is published or accepted here.
                    downstream->buildAndSolveLinearSystemIfNotYetDone(dt);
                    for (int i = 0; i < count; ++i) if (!connected[i])
                        circuits[i]->computeAndGetFlowOrPressureToGiveToZeroDDomainReplacement();
                    downstream->markLinearSystemAsNeedingBuildingAgain();
                    controls.reset(new ControlSystemsManager(dt, false, 0, 1000));
                    for (int i = 0; i < count; ++i)
                        registerControls(*controls, NetlistXmlReader::Instance(), i, circuits[i]);
                    registerControls(*controls, NetlistDownstreamXmlReader::Instance(), 0,
                                     downstream->getNetlistCircuit());
                    std::cout << "STARFISH_OK LOAD" << std::endl;
                    continue;
                }
                require(bool(downstream), "LOAD must precede circuit operations");
                if (command == "SNAPSHOT") {
                    snapshot(circuits, downstream);
                    continue;
                }
                if (command == "START") {
                    int step;
                    input >> step;
                    require(bool(input) && active == -1 && step == accepted + 1,
                            "START requires the next consecutive timestep");
                    active = step;
                    for (const auto& circuit : circuits) circuit->initialiseAtStartOfTimestep();
                    downstream->initialiseAtStartOfTimestep();
                    controls->updateBoundaryConditionControlSystems();
                    downstream->markLinearSystemAsNeedingBuildingAgain();
                    downstream->markLinearSystemAsNeedingUpdatingAgain();
                    trial = false;
                    std::cout << "STARFISH_OK START" << std::endl;
                    continue;
                }
                require(active >= 0, "START must precede queries or acceptance");
                if (command == "ACCEPT") {
                    require(trial, "ACCEPT requires a complete TRIAL");
                    for (const auto& circuit : circuits) circuit->finalizeLPNAtEndOfTimestep();
                    downstream->finalizeLPNAtEndOfTimestep();
                    accepted = active;
                    active = -1;
                    trial = false;
                    std::cout << "STARFISH_OK ACCEPT" << std::endl;
                    continue;
                }
                require(command == "QUERY" || command == "TRIAL", "unknown command");
                for (auto& value : flows) {
                    input >> value;
                    require(bool(input) && std::isfinite(value), "invalid external flow vector");
                }
                for (auto& value : pressures) {
                    input >> value;
                    require(bool(input) && std::isfinite(value), "invalid external pressure vector");
                }
                if (command == "QUERY") {
                    // Explicitly invalidate every probe: no stale global solve reuse.
                    downstream->markLinearSystemAsNeedingBuildingAgain();
                    downstream->buildAndSolveLinearSystemIfNotYetDone(dt);
                    // A port initially blocked by a valve retains its native
                    // one-shot stored-flow guard until it first becomes flow
                    // driven. Discard the first frozen-state solve and repeat
                    // with the requested inputs. Neither query publishes or
                    // accepts circuit state; this also covers later opening.
                    downstream->markLinearSystemAsNeedingBuildingAgain();
                    downstream->buildAndSolveLinearSystemIfNotYetDone(dt);
                    std::vector<std::pair<boundary_data_t,double>> independent(circuits.size());
                    for (int i = 0; i < static_cast<int>(circuits.size()); ++i) if (!connected[i]) {
                        circuits[i]->computeAndGetFlowOrPressureToGiveToZeroDDomainReplacement();
                        independent[i] = circuits[i]->computeAndGetFlowOrPressureToGiveToZeroDDomainReplacement();
                    }
                    std::cout << "STARFISH_OK QUERY";
                    for (int i = 0; i < static_cast<int>(circuits.size()); ++i) {
                        const bool permits = circuits[i]->flowPermittedAcross3DInterface();
                        const double pressure = connected[i] ? downstream->getComputedInterfacePressure(i)
                            : (permits ? independent[i].second : pressures[i]);
                        const double flow = connected[i] ? downstream->getComputedInterfaceFlow(i)
                            : (permits ? flows[i] : independent[i].second * circuits[i]->getInterfaceFlowSign());
                        std::cout << ' ' << circuits[i]->flowPermittedAcross3DInterface()
                                  << ' ' << pressure << ' ' << flow;
                    }
                    std::cout << std::endl;
                } else {
                    downstream->markLinearSystemAsNeedingUpdatingAgain();
                    for (const auto& circuit : circuits) circuit->updateLPN(active);
                    trial = true;
                    snapshot(circuits, downstream);
                }
            } catch (const std::exception& error) {
                std::string message(error.what());
                for (auto& character : message) if (character == '\n') character = ' ';
                std::cout << "STARFISH_ERROR " << message << std::endl;
                status = 1;
                break;
            }
        }
        controls.reset();
        circuits.clear();
        downstream.reset();
        NetlistDownstreamXmlReader::Term();
        NetlistXmlReader::Term();
    }
    if (Py_IsInitialized()) Py_Finalize();
    PetscFinalize();
    return status;
}
