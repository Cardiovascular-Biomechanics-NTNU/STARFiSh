"""
Build STARFiSh networks for the six test cases of

    Boileau et al., A benchmark study of numerical schemes for one-dimensional
    arterial blood flow modelling, Int J Numer Meth Biomed Eng 2015, e02732.

Parameters come from Tables II, III, V, VII, IX and XI of the paper and from the
paper's supplementary material (inflow formulas, 37-artery and ADAN56 meshes).
The ADAN56 case reuses TemplateNetworks/adan56_benchmark2015_template, whose
geometry and Windkessel values match the supplementary mesh.txt.

Usage:
    python make_cases.py <path to SuppMaterial_1DBenchmark_Boileau_etal> [outdir]
"""
import os
import re
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# grid spacing used by the MacCormack (McC) runs in Table I [m]
P_SHIFT = 1.0e4  # [Pa], see vesselXml

MCC_DX = {'singlePulse': 0.00156, 'cca': 0.0039, 'uta': 0.0071, 'aorticBifurcation': 0.0071,
          'artery37': 0.0018, 'adan56': 0.0045}


def laplaceA0(Ad, Pd, E, h):
    """Area at zero transmural pressure for P = Pd + beta/Ad (sqrt(A) - sqrt(Ad))."""
    beta = 4.0 / 3.0 * np.sqrt(np.pi) * E * h
    return (np.sqrt(Ad) - Pd * Ad / beta) ** 2


def readInflow(path):
    """Evaluate the Fourier inflow formula of a supplementary inflow.txt [ml/s]."""
    text = open(path).read()
    T = float(re.search(r'period T=([\d.]+)', text).group(1))
    expr = re.search(r'inflow=(.*)', text).group(1).replace('PI', 'np.pi').replace('sin', 'np.sin')
    t = np.linspace(0.0, T, 2001)
    return T, t, eval(expr, {'np': np, 'T': T, 't': t})


def writeInflowCsv(path, t, Qml):
    with open(path, 'w') as f:
        f.write('t;Q\n')
        for ti, qi in zip(t, Qml):
            f.write('{:.10g};{:.10g}\n'.format(ti, qi * 1e-6))


def nodes(L, dx):
    return max(5, int(round(L / dx)) + 1)


def vesselXml(Id, name, L, rProx, rDist, N, Pd, h, E, left=None, right=None, Pout=0.0):
    """
    STARFiSh aborts on negative pressure, and its Windkessel outlet pressure is -Pext.
    All pressures are therefore shifted by P_SHIFT: with Pext = -(P_SHIFT + Pout) and
    Ps = Pd + P_SHIFT - Pext the tube law sees P - P_SHIFT - Pd, as in the paper, and
    the outlets see P - P_SHIFT - Pout. Subtract P_SHIFT from computed pressures.
    """
    Pext = -(P_SHIFT + Pout)
    Ps = Pd + P_SHIFT - Pext
    return """    <vessel Id="{Id}" name="{name}">
      <topology>
        <leftDaughter>{left}</leftDaughter>
        <rightDaughter>{right}</rightDaughter>
        <angleYMother unit="deg">0</angleYMother>
      </topology>
      <geometry>
        <geometryType>cone</geometryType>
        <length unit="m">{L!r}</length>
        <radiusProximal unit="m">{rProx!r}</radiusProximal>
        <radiusDistal unit="m">{rDist!r}</radiusDistal>
        <N>{N}</N>
      </geometry>
      <compliance>
        <complianceType>Laplace2</complianceType>
        <constantCompliance>False</constantCompliance>
        <externalPressure unit="Pa">{Pext!r}</externalPressure>
        <Ps unit="Pa">{Ps!r}</Ps>
        <As unit="m2">None</As>
        <wallThickness unit="m">{h!r}</wallThickness>
        <youngModulus unit="Pa">{E!r}</youngModulus>
      </compliance>
      <fluid>
        <applyGlobalFluid>True</applyGlobalFluid>
        <my unit="Pa s">0.004</my>
        <rho unit="kg m-3">1050.0</rho>
        <gamma>None</gamma>
      </fluid>
    </vessel>
""".format(Id=Id, name=name, L=float(L), rProx=float(rProx), rDist=float(rDist), N=N, Ps=float(Ps), Pext=float(Pext),
           h=float(h), E=float(E), left=left, right=right)


def inflowXml(csv, T, totalTime, single=False):
    return """      <Flow-FromFile>
        <amp unit="m3 s-1">1.0</amp>
        <ampConst unit="m3 s-1">0.0</ampConst>
        <Npulse>{Np}</Npulse>
        <Tpulse unit="s">0.0</Tpulse>
        <freq unit="s-1">{freq!r}</freq>
        <Tspace unit="s">{Tspace}</Tspace>
        <runtimeEvaluation>False</runtimeEvaluation>
        <filePathName>{csv}</filePathName>
        <prescribe>total</prescribe>
      </Flow-FromFile>
""".format(Np=1 if single else int(np.ceil(totalTime / T)) + 1, freq=1.0 / T,
           Tspace=100.0 if single else 0.0, csv=csv)


def windkesselXml(R1, R2, C, end=False):
    tag = ('_' if end else '') + 'Windkessel-3Elements'
    return """      <{tag}>
        <Rc unit="Pa s m-3">{R2!r}</Rc>
        <Rtotal unit="Pa s m-3">None</Rtotal>
        <C unit="m3 Pa-1">{C!r}</C>
        <Z unit="Pa s m-3">{R1!r}</Z>
      </{tag}>
""".format(tag=tag, R1=float(R1), R2=float(R2), C=float(C))


def networkXml(name, totalTime, saveBegin, saveDt, mu, rho, gamma, Pout, bcs, vessels, init='Auto'):
    """
    STARFiSh prescribes inflow increments, so a run keeps any offset between the initial
    flow and the inflow at t = 0. 'Auto' initialises from the mean inflow and runs an
    initialisation phase that avoids this; 'ConstantPressure' starts at zero flow and
    zero transmural pressure and suits only inflows that start at zero.
    """
    bcText = ''.join('    <boundaryCondition vesselId="{}">\n{}    </boundaryCondition>\n'.format(v, b)
                     for v, b in bcs)
    return """<?xml version='1.0' encoding='ISO-8859-1'?>
<{name}.xml id="1" version="4.3">
  <simulationContext>
    <description>Boileau et al. 2015 benchmark: {name}</description>
    <totalTime unit="s">{totalTime!r}</totalTime>
    <timeSaveBegin unit="s">{saveBegin!r}</timeSaveBegin>
    <minSaveDt unit="s">{saveDt!r}</minSaveDt>
    <maxMemory unit="MB">2000</maxMemory>
    <saveInitialisationPhase>False</saveInitialisationPhase>
    <CFL>0.8</CFL>
    <gravitationalField>False</gravitationalField>
    <gravityConstant unit="m s-2">-9.81</gravityConstant>
    <centralVenousPressure unit="Pa">{Pout!r}</centralVenousPressure>
    <minimumVenousPressure unit="Pa">0.0</minimumVenousPressure>
  </simulationContext>
  <solverCalibration>
    <solvingSchemeField>MacCormack_Flux</solvingSchemeField>
    <rigidAreas>False</rigidAreas>
    <simplifyEigenvalues>False</simplifyEigenvalues>
    <riemannInvariantUnitBase>Pressure</riemannInvariantUnitBase>
    <automaticGridAdaptation>False</automaticGridAdaptation>
  </solverCalibration>
  <initialisationControls>
    <initialsationMethod>{init}</initialsationMethod>
    <initMeanFlow unit="m3 s-1">0.0</initMeanFlow>
    <initMeanPressure unit="Pa">{Pinit!r}</initMeanPressure>
    <estimateWindkesselCompliance>No</estimateWindkesselCompliance>
    <compPercentageWK3>0.8</compPercentageWK3>
    <compPercentageTree>0.2</compPercentageTree>
    <compTotalSys unit="m3 Pa-1">4.895587352e-08</compTotalSys>
  </initialisationControls>
  <globalFluid>
    <my unit="Pa s">{mu!r}</my>
    <rho unit="kg m-3">{rho!r}</rho>
    <gamma>{gamma!r}</gamma>
  </globalFluid>
  <communicators>
  </communicators>
  <boundaryConditions>
{bcs}  </boundaryConditions>
  <generalRandomInputs>
  </generalRandomInputs>
  <vessels>
{vessels}  </vessels>
</{name}.xml>
""".format(name=name, totalTime=float(totalTime), saveBegin=float(saveBegin), saveDt=float(saveDt),
           mu=float(mu), rho=float(rho), gamma=float(gamma), Pout=float(Pout), Pinit=float(P_SHIFT), init=init, bcs=bcText,
           vessels=''.join(vessels))


def save(outdir, case, xml, csv=None, inflow=None):
    d = os.path.join(outdir, case)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, case + '.xml'), 'w').write(xml)
    if csv:
        writeInflowCsv(os.path.join(d, csv), *inflow)
    print('wrote', os.path.join(d, case + '.xml'))


def singlePulse(supp, outdir):
    """Benchmark 1 (Table II, Equation 14): Gaussian pulse in a 10 m vessel, absorbing outlet."""
    L, r, h, E = 10.0, 0.01, 1.5e-3, 400e3
    t = np.linspace(0.0, 0.2, 4001)
    Qml = 1.0 * np.exp(-10000.0 * (t - 0.05) ** 2)
    for visc, mu in (('inviscid', 0.0), ('viscous', 4e-3)):
        case = 'singlePulse_' + visc
        bc = inflowXml('inflow.csv', 0.2, 1.6, single=True) + "      <_ReflectionCoefficient>\n        <Rt>0.0</Rt>\n      </_ReflectionCoefficient>\n"
        xml = networkXml(case, 1.6, 0.0, -1, mu, 1050.0, 9.0, 0.0, [(1, bc)],
                         [vesselXml(1, 'vessel', L, r, r, nodes(L, MCC_DX['singlePulse']), 0.0, h, E)],
                         init='ConstantPressure')
        save(outdir, case, xml, 'inflow.csv', (t, Qml))


def singleArtery(supp, outdir, case, folder, L, rd, h, E, gamma, R1, R2, C, tEnd):
    """Benchmarks 2 and 3: one vessel with a three-element Windkessel (Tables III and V)."""
    T, t, Qml = readInflow(os.path.join(supp, folder, 'inflow.txt'))
    Ad = np.pi * rd ** 2
    A0 = {'cca': 0.22038e-4, 'uta': 3.0605e-4}[case]   # initial (zero-pressure) area from the tables
    beta = 4.0 / 3.0 * np.sqrt(np.pi) * E * h
    Pd = beta / Ad * (np.sqrt(Ad) - np.sqrt(A0))
    bc = inflowXml('inflow.csv', T, tEnd) + windkesselXml(R1, R2, C, end=True)
    xml = networkXml(case, tEnd, tEnd - T, 1e-3, 4e-3, 1060.0, gamma, 0.0, [(1, bc)],
                     [vesselXml(1, case, L, rd, rd, nodes(L, MCC_DX[case]), Pd, h, E)])
    save(outdir, case, xml, 'inflow.csv', (t, Qml))


def aorticBifurcation(supp, outdir):
    """Benchmark 4 (Table VII)."""
    folder = 'Benchmark4_AorticBifurcation'
    T, t, Qml = readInflow(os.path.join(supp, folder, 'inflow.txt'))
    tEnd = 29.7
    dx = MCC_DX['aorticBifurcation']
    vessels, bcs = [], []
    for Id, name, L, rd, A0, h, E in ((1, 'aorta', 0.086, 0.0086, 1.8062e-4, 1.032e-3, 500e3),
                                       (2, 'iliacL', 0.085, 0.0060, 0.94787e-4, 0.72e-3, 700e3),
                                       (3, 'iliacR', 0.085, 0.0060, 0.94787e-4, 0.72e-3, 700e3)):
        Ad = np.pi * rd ** 2
        beta = 4.0 / 3.0 * np.sqrt(np.pi) * E * h
        Pd = beta / Ad * (np.sqrt(Ad) - np.sqrt(A0))
        kids = (2, 3) if Id == 1 else (None, None)
        vessels.append(vesselXml(Id, name, L, rd, rd, nodes(L, dx), Pd, h, E, *kids))
    bcs.append((1, inflowXml('inflow.csv', T, tEnd)))
    for Id in (2, 3):
        bcs.append((Id, windkesselXml(6.8123e7, 3.1013e9, 3.6664e-10)))
    xml = networkXml('aorticBifurcation', tEnd, tEnd - T, 1e-3, 4e-3, 1060.0, 9.0, 0.0, bcs, vessels,
                     )
    save(outdir, 'aorticBifurcation', xml, 'inflow.csv', (t, Qml))


def artery37(supp, outdir):
    """
    Benchmark 5 (Table IX): 37-artery in vitro network with single-resistance outlets
    and outflow pressure 432.6 Pa. A resistance with outflow pressure is modelled as a
    three-element Windkessel with zero compliance and Z = R1.
    """
    folder = 'Benchmark5_37ArteryNetwork'
    T, t, Qml = readInflow(os.path.join(supp, folder, 'inflow.txt'))
    mesh = np.loadtxt(os.path.join(supp, folder, 'mesh.txt'))
    tEnd = 15.0
    dx = MCC_DX['artery37']
    children = {}
    for row in mesh:
        children.setdefault(int(row[1]), []).append(int(row[0]))
    vessels, bcs = [], [(1, inflowXml('inflow.csv', T, tEnd))]
    for row in mesh:
        Id, start, end, L, r0, r1, h = int(row[0]), int(row[1]), int(row[2]), row[3], row[4], row[5], row[6]
        kids = children.get(end, [])
        if len(kids) > 2:
            raise ValueError('segment {} has more than two daughters'.format(Id))
        left = kids[0] if kids else None
        right = kids[1] if len(kids) > 1 else None
        vessels.append(vesselXml(Id, 'segment_{}'.format(Id), L, r0, r1, nodes(L, dx), 0.0, h, 1.2e6, left, right,
                                 Pout=432.6))
        if row[9] > 0:
            bcs.append((Id, windkesselXml(row[9] * 1e9, 1e-6, 0.0)))
    xml = networkXml('artery37', tEnd, 14.0, 1e-3, 2.5e-3, 1050.0, 9.0, 432.6, bcs, vessels)
    save(outdir, 'artery37', xml, 'inflow.csv', (t, Qml))


def adan56(supp, outdir):
    """Benchmark 6 (Table XI): reuse the repository template, run 10 cycles, save the last."""
    src = os.path.join(REPO, 'TemplateNetworks', 'adan56_benchmark2015_template')
    xml = open(os.path.join(src, 'adan56_benchmark2015_template.xml')).read()
    xml = xml.replace('<adan56_benchmark2015.xml', '<adan56.xml').replace('</adan56_benchmark2015.xml>', '</adan56.xml>')
    xml = re.sub(r'<totalTime unit="s">[^<]*<', '<totalTime unit="s">10.0<', xml)
    xml = re.sub(r'<timeSaveBegin unit="s">[^<]*<', '<timeSaveBegin unit="s">9.0<', xml)
    xml = re.sub(r'<minSaveDt unit="s">[^<]*<', '<minSaveDt unit="s">0.001<', xml)
    xml = re.sub(r'<saveInitialisationPhase>[^<]*<', '<saveInitialisationPhase>False<', xml)
    xml = re.sub(r'<filePathName>[^<]*<', '<filePathName>inflow.csv<', xml)
    data = np.loadtxt(os.path.join(supp, 'Benchmark6_ADAN56', 'inflow.txt'))
    d = os.path.join(outdir, 'adan56')
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'adan56.xml'), 'w').write(xml)
    writeInflowCsv(os.path.join(d, 'inflow.csv'), data[:, 0], data[:, 1])
    print('wrote', os.path.join(d, 'adan56.xml'))


def main():
    supp = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'cases')
    singlePulse(supp, outdir)
    singleArtery(supp, outdir, 'cca', 'Benchmark2_CommonCarotidArtery', 0.126, 0.003, 0.3e-3, 700e3, 2.0,
                 2.4875e8, 1.8697e9, 1.7529e-10, 9.9)
    singleArtery(supp, outdir, 'uta', 'Benchmark3_UpperThoracicAorta', 0.24137, 0.012, 1.2e-3, 400e3, 9.0,
                 1.1752e7, 1.1167e8, 1.0163e-8, 20.0)
    aorticBifurcation(supp, outdir)
    artery37(supp, outdir)
    adan56(supp, outdir)


if __name__ == '__main__':
    main()
