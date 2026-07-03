import os
import sys

import numpy as np

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(repo_root)

from UtilityLib import moduleXML
from UtilityLib import networkXml043 as network_xml
from NetworkLib.classCompliance import Hayashi

xml_path = os.path.join(
    repo_root,
    "TemplateNetworks",
    "bigDaddy_Reymond2009_template",
    "bigDaddy_Reymond2009_expr_test.xml",
)

network = moduleXML.loadNetworkFromXML(
    "bigDaddy_Reymond2009_expr_test",
    networkXmlFile=xml_path,
)

rtotal = network.boundaryConditions[49][0].Rtotal
vessel = network.vessels[49]
beta_hayashi = vessel.betaHayashi

print("boundaryConditions[49][0].Rtotal =", rtotal)
print("vessels[49].complianceType =", vessel.complianceType)
print("vessels[49].betaHayashi =", beta_hayashi)

assert rtotal == 2 * 5589920000.0
assert vessel.complianceType == "Hayashi"
assert "betaHayashi" in network_xml.vesselComplianceElements[vessel.complianceType]
assert beta_hayashi == 2 * 16.1290322581

network.initialize(initializeForSimulation=False)

assert isinstance(vessel.compliance, Hayashi)
assert np.allclose(vessel.compliance.betaHayashi, beta_hayashi)
assert np.allclose(vessel.compliance.C0preCalculated, vessel.compliance.C(vessel.Ps))
print("vessels[49].compliance.betaHayashi =", vessel.compliance.betaHayashi)

bc = network.boundaryConditions[49][0]
assert bc.returnFunction == bc.funcPos1

R = np.array([[1.0, 0.5], [0.25, 1.5]])
dt = 0.001
P = 13332.0
Q = 1e-6
Z1 = 1.0
Z2 = 1.0
original_rtotal = bc.Rtotal

omega_original, dq_original = bc.returnFunction(0.0, R, dt, P, Q, Z1, Z2, 0)
bc.Rtotal = original_rtotal * 1.1
omega_changed, dq_changed = bc.returnFunction(0.0, R, dt, P, Q, Z1, Z2, 0)
bc.Rtotal = original_rtotal

assert np.max(np.abs(omega_original - omega_changed)) > 0.0
assert np.max(np.abs(dq_original - dq_changed)) > 0.0
print("boundaryConditions[49][0] runtime output changes when Rtotal changes")

print("Loaded OK")
