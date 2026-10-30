"""
Run one benchmark case with one field scheme, without visualisation, and store
the saved P, Q and A of every vessel in a compressed .npz file.

Usage:
    python run_case.py <case.xml> <scheme> <out.npz>
"""
import os
import sys
import time
import warnings

warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import h5py
import numpy as np
import UtilityLib.moduleXML as mXML
import SolverLib.class1DflowSolver as c1dFS


SNAPSHOT_TIMES = [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5]


def main():
    xml, scheme, out = sys.argv[1], sys.argv[2], sys.argv[3]
    case = os.path.splitext(os.path.basename(xml))[0]
    hdf5 = out.replace('.npz', '.hdf5')

    net = mXML.loadNetworkFromXML(case, '001', networkXmlFile=xml, pathSolutionDataFilename=hdf5)
    net.quiet = True
    net.communicators = {}          # no real-time visualisation
    net.solvingSchemeField = scheme

    start = time.time()
    solver = c1dFS.FlowSolver(net, quiet=True)
    dt, nSteps = net.dt, net.nTSteps
    solveStart = time.time()
    solver.solve()
    solveTime = time.time() - solveStart
    net.saveSolutionData()
    wall = time.time() - start

    result = {'scheme': scheme, 'case': case, 'wall': wall, 'solveTime': solveTime, 'dt': dt, 'nSteps': nSteps}
    with h5py.File(hdf5, 'r') as f:
        t = f['VascularNetwork/simulationTime'][:]
        keep = slice(None)
        if case.startswith('singlePulse'):
            # spatial snapshots: keep the two steps around each output time of the paper
            idx = np.searchsorted(t, SNAPSHOT_TIMES)
            keep = np.unique(np.concatenate([idx - 1, idx]))
        result['t'] = t[keep]
        names = []
        for key in f['vessels']:
            name, Id = [s.strip() for s in key.split(' - ')]
            names.append(name)
            for q in ('P', 'Q', 'A'):
                result['{}/{}'.format(name, q)] = f['vessels'][key][q + 'sol'][keep].astype(np.float32)
            result['{}/Id'.format(name)] = int(Id)
        result['names'] = np.array(names)
    os.remove(hdf5)
    np.savez_compressed(out, **result)
    print('{} {} dt={:.3e} steps={} solve={:.1f}s wall={:.1f}s'.format(case, scheme, dt, nSteps, solveTime, wall))


if __name__ == '__main__':
    main()
