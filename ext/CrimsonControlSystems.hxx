#ifndef STARFISH_CRIMSON_CONTROL_SYSTEMS_HXX
#define STARFISH_CRIMSON_CONTROL_SYSTEMS_HXX

#include <utility>
#include <vector>

#include <boost/shared_ptr.hpp>

class ControlSystemsManager;
class NetlistCircuit;

class CrimsonControlSystems
{
public:
    CrimsonControlSystems(
        double dt,
        bool masterControlScriptPresent,
        int startingTimestep,
        int restartInterval);

    void initialize(
        const std::vector<
            std::pair<int, boost::shared_ptr<NetlistCircuit> >
        >& circuits);

    void update();

    int controllerCount() const;

private:
    boost::shared_ptr<ControlSystemsManager> manager_;
    bool initialized_;
};

#endif
