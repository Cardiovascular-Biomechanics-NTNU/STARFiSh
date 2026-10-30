"""
Compare benchmark runs (run_case.py output) with the reference data of Boileau et al. 2015.

Error metrics follow Equations (10)-(13) of the paper: pressure errors are relative to
the reference pointwise, flow-type errors (Q, change in radius, pressure difference)
are normalised by the maximum of the reference over the cycle. The paper's six 1D
schemes are scored with the same code, so every number in the output is comparable.

Usage:
    python compare.py <SuppMaterial dir> <results dir> <cases dir> <out.json>

STARFiSh's 'Auto' initialisation starts the saved time axis at a shifted phase of
the inflow. Each run's delay is measured by matching the flow at the inlet node
with the prescribed inflow, and the run's time axis is corrected by it.
"""
import glob
import json
import os
import sys

import numpy as np

P_SHIFT = 1.0e4   # pressure shift of the generated cases, see make_cases.py
PAPER = ['DCG', 'LCG', 'FEM', 'FVM', 'McC', 'STM']
SCHEMES = ['MacCormack_Flux', 'MacCormack_Matrix', 'LaxWendroff', 'TaylorGalerkin', 'FV_MUSCL_HLL',
           'FV_MUSCL_Rusanov', 'MUSCL_Hancock', 'ADER3', 'DG_P2']
PULSE_TIMES = [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5]


def metrics(sim, ref, relative):
    """Equations (10)-(13); relative=True for pressure, else normalised by max(ref)."""
    scale = np.abs(ref) if relative else np.max(np.abs(ref))
    e = (sim - ref) / scale
    return {'RMS': 100 * float(np.sqrt(np.mean(e ** 2))),
            'MAX': 100 * float(np.max(np.abs(e))),
            'SYS': 100 * float((sim.max() - ref.max()) / (ref.max() if relative else np.max(np.abs(ref)))),
            'DIAS': 100 * float((sim.min() - ref.min()) / (ref.min() if relative else np.max(np.abs(ref))))}


# root vessel and inflow period of the cases with a periodic inflow
INFLOW = {'cca': ('cca', 1.1), 'uta': ('uta', 0.955), 'aorticBifurcation': ('aorta', 1.1),
          'artery37': ('segment_1', 0.827), 'adan56': ('aortic_arch_I', 1.0)}
CASES_DIR = None


def inflowDelay(d, case):
    root, T = INFLOW[case]
    q = np.loadtxt(os.path.join(CASES_DIR, case, 'inflow.csv'), delimiter=';', skiprows=1)
    t, Q = d['t'], d['{}/Q'.format(root)][:, 0].astype(float)
    shifts = np.arange(-T / 2, T / 2, 2e-4)
    err = [np.mean((Q - np.interp(np.mod(t - s, T), q[:, 0], q[:, 1])) ** 2) for s in shifts]
    return float(shifts[int(np.argmin(err))])


class Run(object):
    def __init__(self, path, shifted=True, case=None):
        self.d = np.load(path, allow_pickle=False)
        self.delay = inflowDelay(self.d, case) if case in INFLOW else 0.0
        self.t = self.d['t'] - self.delay
        self.period = INFLOW[case][1] if case in INFLOW else None
        self.shift = P_SHIFT if shifted else 0.0
        self.scheme = str(self.d['scheme'])
        self.solveTime = float(self.d['solveTime'])
        self.nSteps = int(self.d['nSteps'])

    def interp(self, tt, y):
        """Sample a saved series at times tt. The periodic cases save one converged cycle,
        so times outside it (the delay correction moves the window) wrap by one period."""
        if self.period:
            tt = self.t[0] + np.mod(np.asarray(tt) - self.t[0], self.period)
        return np.interp(tt, self.t, y)

    def at(self, vessel, frac):
        """P [kPa], Q [ml/s], A [m2] over time at a relative position along a vessel."""
        out = []
        for q in ('P', 'Q', 'A'):
            field = self.d['{}/{}'.format(vessel, q)].astype(float)
            x = frac * (field.shape[1] - 1)
            i = min(int(np.floor(x)), field.shape[1] - 2)
            w = x - i
            out.append((1 - w) * field[:, i] + w * field[:, i + 1])
        P, Q, A = out
        return (P - self.shift) / 1e3, Q * 1e6, A

    def node(self, vessel, q, i):
        return self.d['{}/{}'.format(vessel, q)][:, i].astype(float)


def results(resultsDir, case):
    runs = {}
    for s in SCHEMES:
        f = os.path.join(resultsDir, '{}_{}.npz'.format(case, s))
        if os.path.isfile(f):
            runs[s] = Run(f, shifted=(case != 'adan56'), case=case)
    return runs


def timing(runs):
    return {s: {'solveTime': r.solveTime, 'nSteps': r.nSteps, 'inflowDelay': r.delay} for s, r in runs.items()}


# --- benchmark 1 -------------------------------------------------------------

def singlePulse(supp, resultsDir, visc):
    D = glob.glob(os.path.join(supp, 'Benchmark1*', 'NumData'))[0]
    refs = {k: np.loadtxt(os.path.join(D, '{}_{}.txt'.format(k, visc))) for k in PAPER}
    dcg = refs['DCG']

    def score(x, snapshots):
        errs, peak = [], None
        for j, P in enumerate(snapshots):
            Pi = np.interp(dcg[:, 0], x, P)
            errs.append(np.sqrt(np.mean((Pi - dcg[:, j + 1]) ** 2)) / dcg[:, j + 1].max())
        peak = snapshots[-1].max() / dcg[:, -1].max() - 1
        return {'RMS': 100 * float(np.mean(errs)), 'peak15': 100 * float(peak)}

    out = {'paper': {}, 'ours': {}, 'profiles': {}}
    for k, r in refs.items():
        if k != 'DCG':
            out['paper'][k] = score(r[:, 0], [r[:, j + 1] for j in range(8)])
    xs = dcg[:, 0]
    sel = (xs >= 8.0) & (xs <= 10.0)
    out['profiles']['x'] = xs[sel][::4].tolist()
    out['profiles']['DCG'] = dcg[sel, 8][::4].tolist()
    runs = results(resultsDir, 'singlePulse_' + visc)
    for s, run in runs.items():
        P = (run.d['vessel/P'].astype(float) - run.shift) / 1e3
        x = np.linspace(0.0, 10.0, P.shape[1])
        snaps = []
        for tt in PULSE_TIMES:
            i = np.searchsorted(run.t, tt)
            w = (tt - run.t[i - 1]) / (run.t[i] - run.t[i - 1])
            snaps.append((1 - w) * P[i - 1] + w * P[i])
        out['ours'][s] = score(x, snaps)
        out['profiles'][s] = np.interp(out['profiles']['x'], x, snaps[-1]).tolist()
    out['timing'] = timing(runs)
    return out


# --- benchmarks 2-4 ----------------------------------------------------------

SINGLE = {
    'cca': dict(folder='Benchmark2', tini=8.8, T=1.1, shift3d=0.056, rd=0.003,
                sites={'Mid': ('cca', 0.5, '3D.txt', '{}.txt')}),
    'uta': dict(folder='Benchmark3', tini=19.045, T=0.955, shift3d=0.055, rd=0.012,
                sites={'Mid': ('uta', 0.5, '3D.txt', '{}.txt')}),
    'aorticBifurcation': dict(folder='Benchmark4', tini=28.6, T=1.1, shift3d=0.0,
                              rd={'aorta': 0.0086, 'iliacL': 0.006},
                              sites={'AortaMid': ('aorta', 0.5, '3D_AortaMid.txt', '{}_AortaMid.txt'),
                                     'Junction': ('aorta', 1.0, '3D_Junction.txt', '{}_Junction.txt'),
                                     'IliacMid': ('iliacL', 0.5, '3D_IliacMid.txt', '{}_IliacMid.txt')}),
}


def physiological(supp, resultsDir, case):
    cfg = SINGLE[case]
    D = glob.glob(os.path.join(supp, cfg['folder'] + '*', 'NumData'))[0]
    runs = results(resultsDir, case)
    out = {'sites': {}, 'timing': timing(runs)}
    for site, (vessel, frac, ref3d, ref1d) in cfg['sites'].items():
        r3 = np.loadtxt(os.path.join(D, ref3d))
        tt = cfg['tini'] + np.mod(r3[:, 0] + cfg['shift3d'], cfg['T'])
        order = np.argsort(tt)
        quantities = {'P': (1, True), 'Q': (2, False), 'dr': (3, False)}
        if r3.shape[1] > 4:
            quantities['dP'] = (4, False)
        siteOut = {'paper': {}, 'ours': {}, 'waveforms': {'t': (tt[order] - cfg['tini']).tolist(),
                                                           '3D_P': r3[order, 1].tolist(), '3D_Q': r3[order, 2].tolist()}}
        for k in PAPER:
            d = np.loadtxt(os.path.join(D, ref1d.format(k)))
            siteOut['paper'][k] = {q: metrics(np.interp(tt, d[:, 0], d[:, c]), r3[:, c], rel)
                                   for q, (c, rel) in quantities.items()}
        rd = cfg['rd'][vessel] if isinstance(cfg['rd'], dict) else cfg['rd']
        for s, run in runs.items():
            P, Q, A = run.at(vessel, frac)
            series = {'P': P, 'Q': Q, 'dr': (np.sqrt(A / np.pi) - rd) * 1e3}
            if 'dP' in quantities:
                series['dP'] = ((run.node(vessel, 'P', 0) - run.node(vessel, 'P', -1)) / 1e3)
            siteOut['ours'][s] = {q: metrics(run.interp(tt, series[q]), r3[:, c], rel)
                                  for q, (c, rel) in quantities.items()}
            siteOut['waveforms'][s + '_P'] = run.interp(tt[order], P).tolist()
            siteOut['waveforms'][s + '_Q'] = run.interp(tt[order], Q).tolist()
        out['sites'][site] = siteOut
    return out


# --- benchmark 5 -------------------------------------------------------------

SITES37 = ['AorticArchII', 'ThoracicAortaII', 'LSubclavianI', 'RIliacFemoralII', 'LUlnar',
           'RAnteriorTibial', 'RUlnar', 'Splenic']


def artery37(supp, resultsDir):
    base = glob.glob(os.path.join(supp, 'Benchmark5*'))[0]
    shifts = open(os.path.join(base, 'time_shifts.txt'), encoding='utf-16').read().split()
    windows = {}
    for i, token in enumerate(shifts):
        if token in SITES37:
            windows[token] = float(shifts[i + 3])
    runs = results(resultsDir, 'artery37')
    out = {'sites': {}, 'timing': timing(runs), 'segments': {}}
    if 'MacCormack_Flux' not in runs:
        return out
    mcc = {q: np.loadtxt(os.path.join(base, 'NumData', 'McC_{}.txt'.format(q))) for q in ('P', 'Q')}
    names = [str(n) for n in runs['MacCormack_Flux'].d['names']]
    for j, site in enumerate(SITES37):
        tini = windows[site]
        exp = {q: np.loadtxt(os.path.join(base, 'ExpData', '{}_{}.txt'.format(site, q))) for q in ('P', 'Q')}
        tt = tini + exp['P'][:, 0]
        # identify the segment: its midpoint flow best matches the paper's McC solution
        # (pressure is too similar across the network to tell segments apart)
        refQ = np.interp(tt, mcc['Q'][:, 0], mcc['Q'][:, j + 1])
        best = min(names, key=lambda n: np.mean((runs['MacCormack_Flux'].interp(tt, runs['MacCormack_Flux'].at(n, 0.5)[1]) - refQ) ** 2))
        out['segments'][site] = best
        siteOut = {'paper': {}, 'ours': {}}
        for k in PAPER:
            d = {q: np.loadtxt(os.path.join(base, 'NumData', '{}_{}.txt'.format(k, q))) for q in ('P', 'Q')}
            siteOut['paper'][k] = {q: metrics(np.interp(tini + exp[q][:, 0], d[q][:, 0], d[q][:, j + 1]),
                                              exp[q][:, 1], q == 'P') for q in ('P', 'Q')}
        for s, run in runs.items():
            P, Q, _ = run.at(best, 0.5)
            series = {'P': P, 'Q': Q}
            siteOut['ours'][s] = {q: metrics(run.interp(tini + exp[q][:, 0], series[q]), exp[q][:, 1], q == 'P')
                                  for q in ('P', 'Q')}
        out['sites'][site] = siteOut
    return out


# --- benchmark 6 -------------------------------------------------------------

SITES56 = [('AorticArchI', 'aortic_arch_I'), ('ThoAortaIII', 'thoracic_aorta_III'), ('AbdomAortaV', 'abdominal_aorta_V'),
           ('RightCCA', 'common_carotid_R'), ('RightRenal', 'renal_R'), ('RightCommonIliac', 'common_iliac_R'),
           ('RightICA', 'internal_carotid_R'), ('RightRadial', 'radial_R'), ('RightInternalIliac', 'internal_iliac_R'),
           ('RightPOstInteross', 'posterior_interosseous_R'), ('RightFemoralII', 'femoral_R_II'),
           ('RightAntTibial', 'anterior_tibial_R')]


def adan56(supp, resultsDir):
    D = glob.glob(os.path.join(supp, 'Benchmark6*', 'NumData'))[0]
    refs = {k: {q: np.loadtxt(os.path.join(D, '{}_{}.txt'.format(k, q))) for q in ('P', 'Q')} for k in PAPER}
    runs = results(resultsDir, 'adan56')
    out = {'sites': {}, 'timing': timing(runs)}
    for j, (site, vessel) in enumerate(SITES56):
        # no 3D solution exists; the reference is the median of the paper's six schemes,
        # which is robust to the spikes in some of the supplementary files
        tt = np.linspace(9.0, 10.0, 1001)
        paper = {k: {q: np.interp(tt, refs[k][q][:, 0], refs[k][q][:, j + 1]) for q in ('P', 'Q')} for k in PAPER}
        ref = {q: np.median([paper[k][q] for k in PAPER], axis=0) for q in ('P', 'Q')}
        siteOut = {'paper': {}, 'ours': {}}
        for k in PAPER:
            siteOut['paper'][k] = {q: metrics(np.interp(tt, refs[k][q][:, 0], refs[k][q][:, j + 1]), ref[q], q == 'P')
                                   for q in ('P', 'Q')}
        for s, run in runs.items():
            P, Q, _ = run.at(vessel, 0.5)
            siteOut['ours'][s] = {q: metrics(run.interp(tt, v), ref[q], q == 'P') for q, v in (('P', P), ('Q', Q))}
        if j < 3:
            siteOut['waveforms'] = {'t': (tt - 9.0).tolist(), 'ref_P': ref['P'].tolist(), 'ref_Q': ref['Q'].tolist()}
            for s, run in runs.items():
                P, Q, _ = run.at(vessel, 0.5)
                siteOut['waveforms'][s + '_P'] = run.interp(tt, P).tolist()
                siteOut['waveforms'][s + '_Q'] = run.interp(tt, Q).tolist()
        out['sites'][site] = siteOut
    return out


def main():
    global CASES_DIR
    supp, resultsDir, CASES_DIR, outPath = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    summary = {
        'singlePulse_inviscid': singlePulse(supp, resultsDir, 'inviscid'),
        'singlePulse_viscous': singlePulse(supp, resultsDir, 'viscous'),
        'cca': physiological(supp, resultsDir, 'cca'),
        'uta': physiological(supp, resultsDir, 'uta'),
        'aorticBifurcation': physiological(supp, resultsDir, 'aorticBifurcation'),
        'artery37': artery37(supp, resultsDir),
        'adan56': adan56(supp, resultsDir),
    }
    json.dump(summary, open(outPath, 'w'))

    # console summary: RMS pressure / flow error, paper range in brackets
    for case, res in summary.items():
        print('==', case)
        if case.startswith('singlePulse'):
            pr = [v['RMS'] for v in res['paper'].values()]
            print('  paper schemes vs DCG: RMS {:.2f}-{:.2f}%'.format(min(pr), max(pr)))
            for s, v in res['ours'].items():
                print('  {:18s} RMS {:5.2f}%  peak@1.5s {:+.2f}%  solve {:7.1f}s'.format(
                    s, v['RMS'], v['peak15'], res['timing'][s]['solveTime']))
            continue
        for site, so in res['sites'].items():
            pP = [v['P']['RMS'] for v in so['paper'].values()]
            pQ = [v['Q']['RMS'] for v in so['paper'].values()]
            print('  {} paper: P {:.2f}-{:.2f}%  Q {:.2f}-{:.2f}%'.format(site, min(pP), max(pP), min(pQ), max(pQ)))
            for s, v in so['ours'].items():
                print('    {:18s} P {:5.2f}%  Q {:5.2f}%'.format(s, v['P']['RMS'], v['Q']['RMS']))


if __name__ == '__main__':
    main()
