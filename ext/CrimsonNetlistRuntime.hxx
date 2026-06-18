#ifndef STARFISH_CRIMSON_NETLIST_RUNTIME_HXX
#define STARFISH_CRIMSON_NETLIST_RUNTIME_HXX

#include <map>
#include <string>
#include <utility>
#include <vector>

#include <boost/shared_ptr.hpp>

class CrimsonControlSystems;
class NetlistCircuit;

/**
 * Owns the complete CRIMSON netlist state used by one STARFiSh simulation.
 *
 * This class is transport-independent: it does not know about nanobind,
 * Python 3, pipes, or the STARFiSh characteristic equations. A caller supplies
 * interface flow/pressure values and receives CRIMSON's affine boundary law:
 *
 *     P = dp_dq * Q + Hop
 *
 * Keeping circuit ownership here allows the same lifecycle to run inside the
 * future isolated Python 2 executable without duplicating netlist logic in a
 * communication wrapper.
 */
class CrimsonNetlistRuntime
{
public:
    CrimsonNetlistRuntime(
        int hstep,
        double alfi,
        double dt,
        int startingTimestep,
        int restartInterval,
        bool masterControlScriptPresent);

    /**
     * Load the global netlist XML and create one CRIMSON circuit for each
     * surface. Sorted surface IDs map deterministically to XML circuit order.
     */
    void load(
        const std::string& netlistXml,
        const std::vector<int>& surfaceIds);

    // Set where CRIMSON pressure, flow, and volume histories are written.
    void setOutputDirectory(const std::string& outputDirectory);

    // Prepare every circuit once at the beginning of a global timestep.
    void startTimestep(
        int timestep,
        double time);

    // Return (dp_dq, Hop) using CRIMSON's solve-phase alpha*dt scaling.
    std::pair<double, double> computeCoefficients(
        int surfaceId,
        int timestep,
        double time,
        double flow);

    // Return coefficients using CRIMSON's update-phase dt scaling.
    std::pair<double, double> computeUpdateCoefficients(
        int surfaceId,
        int timestep,
        double time,
        double flow);

    bool flowPermitted(int surfaceId);

    bool boundaryConditionTypeChanged(int surfaceId);

    // Supply the final STARFiSh interface state and solve the corresponding LPN.
    void updateState(
        int surfaceId,
        int timestep,
        double pressure,
        double flow);

    /**
     * Finalize all circuits once after every surface has received its final
     * state. This is also the eventual controller-update boundary.
     */
    void finalizeTimestep(int timestep);

    int controllerCount() const;

private:
    /**
     * Stable scalar storage is required because NetlistCircuit retains raw
     * pointers to pressure and flow, matching CRIMSON's original Fortran
     * coupling.
     */
    struct SurfaceState
    {
        SurfaceState();

        double pressure;
        double flow;
        int netlistIndex;
        int nextTimestepWriteStart;
        boost::shared_ptr<NetlistCircuit> circuit;
    };

    SurfaceState& getSurface(int surfaceId);
    void createSurface(int surfaceId, int netlistIndex);
    void initializeControlSystems();
    void requireLoaded() const;

    int hstep_;
    double alfi_;
    double dt_;
    int startingTimestep_;
    int restartInterval_;
    bool masterControlScriptPresent_;

    std::string netlistXml_;
    std::string outputDirectory_;

    // surfaceId -> circuit and persistent interface state.
    std::map<int, SurfaceState> surfaces_;
    boost::shared_ptr<CrimsonControlSystems> controlSystems_;

    // Guards the once-per-global-timestep lifecycle.
    bool loaded_;
    bool timestepStarted_;
    bool timestepFinalized_;
    int currentTimestep_;
};

#endif
