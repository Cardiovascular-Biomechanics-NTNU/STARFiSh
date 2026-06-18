#include "CrimsonControlSystems.hxx"

#include "ControlSystemsManager.hxx"
#include "NetlistXmlReader.hxx"

#include <map>
#include <stdexcept>

CrimsonControlSystems::CrimsonControlSystems(
    double dt,
    bool masterControlScriptPresent,
    int startingTimestep,
    int restartInterval)
    : manager_(new ControlSystemsManager(
          dt,
          masterControlScriptPresent,
          startingTimestep,
          restartInterval)),
      initialized_(false)
{
}

void CrimsonControlSystems::initialize(
    const std::vector<
        std::pair<int, boost::shared_ptr<NetlistCircuit> >
    >& circuits)
{
    if (initialized_) {
        return;
    }

    NetlistXmlReader* reader = NetlistXmlReader::Instance();

    const std::map<int, std::map<int, ComponentControlSpecificationContainer> >&
        componentControls =
            reader->getMapsOfComponentControlTypesForEachSurface();

    const std::map<int, std::map<int, parameter_controller_t> >&
        nodeControls =
            reader->getMapsOfNodalControlTypesForEachSurface();

    for (std::vector<
             std::pair<int, boost::shared_ptr<NetlistCircuit> >
         >::const_iterator circuitEntry = circuits.begin();
         circuitEntry != circuits.end();
         ++circuitEntry) {
        const int netlistIndex = circuitEntry->first;
        const boost::shared_ptr<NetlistCircuit>& circuit = circuitEntry->second;

        std::map<
            int,
            std::map<int, ComponentControlSpecificationContainer>
        >::const_iterator componentMap = componentControls.find(netlistIndex);

        if (componentMap != componentControls.end()) {
            for (std::map<
                     int,
                     ComponentControlSpecificationContainer
                 >::const_iterator component = componentMap->second.begin();
                 component != componentMap->second.end();
                 ++component) {
                for (int controlIndex = 0;
                     controlIndex < component->second.getNumberOfControlScripts();
                     ++controlIndex) {
                    manager_->createParameterController(
                        component->second.getControlTypeByIndexLocalToComponent(
                            controlIndex),
                        circuit,
                        component->first);
                }
            }
        }

        std::map<int, std::map<int, parameter_controller_t> >::const_iterator
            nodeMap = nodeControls.find(netlistIndex);

        if (nodeMap != nodeControls.end()) {
            for (std::map<int, parameter_controller_t>::const_iterator node =
                     nodeMap->second.begin();
                 node != nodeMap->second.end();
                 ++node) {
                manager_->createParameterController(
                    node->second,
                    circuit,
                    node->first);
            }
        }
    }

    initialized_ = true;
}

void CrimsonControlSystems::update()
{
    if (!initialized_) {
        throw std::runtime_error(
            "CrimsonControlSystems must be initialized before update().");
    }

    manager_->updateBoundaryConditionControlSystems();
}

int CrimsonControlSystems::controllerCount() const
{
    return manager_->getNumberOfControlSystems();
}
