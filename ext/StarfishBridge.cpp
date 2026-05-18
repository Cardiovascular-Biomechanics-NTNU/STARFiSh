#include "NetlistCircuit.hxx"
#include <petscsys.h>  // Essential for PetscInitialize
#include <string>
#include <stdexcept>
#include <utility>

class StarfishBridge {
public:
    StarfishBridge(int hstep, double alfi, double delt)
        : m_hstep(hstep),
          m_alfi(alfi),
          m_delt(delt),
          m_pressure(0.0),
          m_flow(0.0),
          m_loaded(false),
          m_timestepStarted(false),
          m_timestepFinalized(false),
          m_currentTimestep(-1) {
        // 1. Initialize PETSc if it hasn't been started yet
        // This is a mechanical necessity for NetlistCircuit to function.
        PetscBool initialized;
        PetscInitialized(&initialized);
        if (!initialized) {
            PetscInitialize(NULL, NULL, NULL, NULL);
        }

        // 2. Use the 7-argument PUBLIC constructor
        // Signature: (hstep, surfaceIndex, LPNIndex, isRestart, alfi, delt, startStep)
        // i. hstep (int)
        // ii. indexOfThisNetlistLPN (int) -> We'll use 0 for the first/only circuit
        // iii. isRestarted (bool)          -> false
        // iv. alfi (double)               -> alfi
        // v. delt (double)               -> delt
        // vi. startingStep (int)          -> 0
        // We use 0 for surfaceIndex and LPNIndex as defaults for your coupling.
        m_circuit = boost::shared_ptr<NetlistCircuit>(
            new NetlistCircuit(hstep, 0, 0, false, alfi, delt, 0)
        );
    }

    void load(const std::string& xml_path) {
        // Ensure the filename is set before triggering the description build
        m_circuit->setNetlistXmlFileName(xml_path);
        m_circuit->setPressureAndFlowPointers(&m_pressure, &m_flow);
        m_circuit->createCircuitDescription();
        m_circuit->closeAllDiodes();
        m_circuit->detectWhetherClosedDiodesStopAllFlowAt3DInterface();
        m_circuit->initialiseCircuit();
        m_loaded = true;
    }

    std::pair<double, double> compute_implicit_coefficients(int timestep,
                                                            double time,
                                                            double dt,
                                                            double flow) {
        ensure_loaded();
        ensure_dt_matches(dt);
        begin_timestep_if_needed(timestep);

        m_flow = flow;
        double alfi_delt = m_alfi * m_delt;
        return m_circuit->computeImplicitCoefficients(timestep, time, alfi_delt);
    }

    void update_state(int timestep,
                      double time,
                      double dt,
                      double pressure,
                      double flow) {
        ensure_loaded();
        ensure_dt_matches(dt);
        begin_timestep_if_needed(timestep);

        m_pressure = pressure;
        m_flow = flow;
        m_circuit->updateLPN(timestep);
    }

    void finalize_timestep(int timestep) {
        ensure_loaded();
        if (m_timestepFinalized && m_currentTimestep == timestep) {
            return;
        }
        m_circuit->finalizeLPNAtEndOfTimestep();
        m_timestepFinalized = true;
    }

private:
    void ensure_loaded() const {
        if (!m_loaded) {
            throw std::runtime_error("StarfishBridge.load(xml_path) must be called before using the netlist.");
        }
    }

    void ensure_dt_matches(double dt) const {
        if (dt != m_delt) {
            throw std::runtime_error("StarfishBridge was constructed with fixed delt; received a different dt.");
        }
    }

    void begin_timestep_if_needed(int timestep) {
        if (m_timestepStarted && m_currentTimestep == timestep) {
            return;
        }
        m_circuit->initialiseAtStartOfTimestep();
        m_currentTimestep = timestep;
        m_timestepStarted = true;
        m_timestepFinalized = false;
    }

    int m_hstep;
    double m_alfi;
    double m_delt;
    double m_pressure;
    double m_flow;
    bool m_loaded;
    bool m_timestepStarted;
    bool m_timestepFinalized;
    int m_currentTimestep;
    boost::shared_ptr<NetlistCircuit> m_circuit;
};
