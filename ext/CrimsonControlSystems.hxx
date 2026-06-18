#ifndef STARFISH_CRIMSON_CONTROL_SYSTEMS_HXX
#define STARFISH_CRIMSON_CONTROL_SYSTEMS_HXX

#include <utility>
#include <vector>

#include <boost/shared_ptr.hpp>

class ControlSystemsManager;
class NetlistCircuit;

/**
 * Thin adapter around CRIMSON's existing ControlSystemsManager.
 *
 * It recreates the controller-registration loops from
 * BoundaryConditionManager::createControlSystems(); controller execution and
 * parameter mutation remain entirely inside CRIMSON.
 */
class CrimsonControlSystems
{
public:
    CrimsonControlSystems(
        double dt,
        bool masterControlScriptPresent,
        int startingTimestep,
        int restartInterval);

    /**
     * Register component and node controllers for each
     * (netlist index, circuit) pair after all circuits are initialized.
     */
    void initialize(
        const std::vector<
            std::pair<int, boost::shared_ptr<NetlistCircuit> >
        >& circuits);

    // Execute CRIMSON's ordered Python/native controller update.
    void update();

    int controllerCount() const;

private:
    boost::shared_ptr<ControlSystemsManager> manager_;
    bool initialized_;
};

#endif
