"""
Conservative field solvers for the 1D blood flow equations in (A, Q) form.

    dA/dt + dQ/dx = 0
    dQ/dt + d/dx( alpha Q^2/A + Fp(A) ) = - Kr Q/A + A g,   Fp(A) = beta (A^(3/2) - As^(3/2)) / (3 rho)

with the Laplace tube law P = P0 + beta (sqrt(A) - sqrt(As)), which is the law
used by the Laplace and Laplace2 compliance models.

Tapering (beta and As varying along the vessel) is handled by hydrostatic
reconstruction: the tube-law parameters are constant within each cell, and at
every face the states of both neighbours are mapped at equal pressure to a
common face geometry before the face flux is computed. Each cell then receives
a pressure-flux correction for the difference between its own geometry and the
face geometry. A state at rest (Q = 0, uniform P) is preserved exactly for any
pressure, and mass is conserved exactly. Without this, the large geometric
flux and source terms do not cancel on coarse, strongly tapered vessels.

Each class is a drop-in replacement for classFields.Field: called once per
global time step, it reads P, Q, A at memory index n and writes the interior
nodes at n+1. Boundary nodes (0 and N-1) are written by the boundary and
connection objects through the characteristics, as for the MacCormack scheme.
Here they act as fixed ghost states during the step.

Nodes are treated as cell centres of width dz. When the global time step is
larger than a scheme's stable step, the field sub-cycles internally.

Schemes (solvingSchemeField):
    LaxWendroff        two-step Richtmyer Lax-Wendroff, 2nd order
    TaylorGalerkin     two-step Taylor-Galerkin, linear elements, consistent mass, 2nd order
    FV_MUSCL_HLL       finite volume, MUSCL (van Leer limiter), HLL flux, SSP-RK2, 2nd order
    FV_MUSCL_Rusanov   as above with the Rusanov (local Lax-Friedrichs) flux
    MUSCL_Hancock      finite volume, MUSCL-Hancock predictor, HLL flux, 2nd order
    ADER3              finite volume ADER, CWENO3 reconstruction and local space-time
                       Galerkin predictor, HLL flux, 3rd order
    DG_P2              modal discontinuous Galerkin (Legendre P2), HLL flux, SSP-RK3
"""
import numpy as np
from scipy.linalg import solve_banded


class ConservativeField(object):

    cflLimit = 0.9

    def __init__(self, vessel, currentMemoryIndex, dt, systemEquation, rigidArea):
        self.name = ' '.join([type(self).__name__, str(vessel.Id)])
        if rigidArea:
            raise ValueError("{}: rigid areas are not supported by conservative schemes".format(self.name))
        compliance = vessel.compliance
        if type(compliance).__name__ not in ('Laplace', 'Laplace2'):
            raise ValueError("{}: conservative schemes need a Laplace or Laplace2 compliance model, got {}".format(
                self.name, type(compliance).__name__))

        self.vessel = vessel
        self.currentMemoryIndex = currentMemoryIndex
        self.dt = dt
        self.P = vessel.Psol
        self.Q = vessel.Qsol
        self.A = vessel.Asol
        self.N = len(vessel.z)

        dz = np.asarray(vessel.dz, dtype=float)
        if not np.allclose(dz, dz[0], rtol=1e-8):
            raise ValueError("{}: conservative schemes need equidistant grids".format(self.name))
        self.dx = float(dz[0])

        self.rho = vessel.rho
        self.alpha = (vessel.gamma + 2.0) / (vessel.gamma + 1.0)
        self.Kr = 2.0 * (vessel.gamma + 2.0) * np.pi * vessel.my / vessel.rho
        self.netGravity = vessel.netGravity
        self.P0 = compliance.externalPressure + compliance.Ps

        # tube law parameters per cell, at the faces, and of the cells left and right of each face
        beta = np.ones(self.N) * compliance.betaLaplace
        sqrtAs = np.ones(self.N) * np.sqrt(compliance.As)
        self.cell = {'beta': beta, 'sqrtAs': sqrtAs}
        self.face = {'beta': 0.5 * (beta[1:] + beta[:-1]), 'sqrtAs': 0.5 * (sqrtAs[1:] + sqrtAs[:-1])}
        self.faceLeft = {key: value[:-1] for key, value in self.cell.items()}
        self.faceRight = {key: value[1:] for key, value in self.cell.items()}
        self.inner = {key: value[1:-1] for key, value in self.cell.items()}
        self.setup()

    def setup(self):
        pass

    # --- physics -------------------------------------------------------------

    def pressure(self, A, geo):
        return self.P0 + geo['beta'] * (np.sqrt(A) - geo['sqrtAs'])

    def area(self, P, geo):
        return ((P - self.P0) / geo['beta'] + geo['sqrtAs']) ** 2

    def pressureFlux(self, A, geo):
        return geo['beta'] * (A ** 1.5 - geo['sqrtAs'] ** 3) / (3.0 * self.rho)

    def flux(self, U, geo):
        A, Q = U[0], U[1]
        return np.array([Q, self.alpha * Q * Q / A + self.pressureFlux(A, geo)])

    def source(self, U):
        """Viscous friction and gravity; tapering enters through the face corrections."""
        A, Q = U[0], U[1]
        g = self.netGravity[self.n]
        g = g[0] if np.ndim(g) else g
        return np.array([np.zeros_like(A), -self.Kr * Q / A + A * g])

    def eigenvalues(self, U, geo):
        A, Q = U[0], U[1]
        u = Q / A
        c2 = geo['beta'] * np.sqrt(A) / (2.0 * self.rho)
        root = np.sqrt(c2 + self.alpha * (self.alpha - 1.0) * u * u)
        return self.alpha * u - root, self.alpha * u + root

    def hll(self, UL, UR, geo):
        lL1, lL2 = self.eigenvalues(UL, geo)
        lR1, lR2 = self.eigenvalues(UR, geo)
        SL = np.minimum(np.minimum(lL1, lR1), 0.0)
        SR = np.maximum(np.maximum(lL2, lR2), 0.0)
        FL, FR = self.flux(UL, geo), self.flux(UR, geo)
        return (SR * FL - SL * FR + SL * SR * (UR - UL)) / (SR - SL)

    def rusanov(self, UL, UR, geo):
        lL1, lL2 = self.eigenvalues(UL, geo)
        lR1, lR2 = self.eigenvalues(UR, geo)
        smax = np.max(np.abs([lL1, lL2, lR1, lR2]), axis=0)
        return 0.5 * (self.flux(UL, geo) + self.flux(UR, geo)) - 0.5 * smax * (UR - UL)

    riemann = hll

    # --- hydrostatic reconstruction --------------------------------------------

    def corrections(self, PL, PR, AfL, AfR):
        """Momentum flux corrections for the cells left and right of each face."""
        fixL = self.pressureFlux(self.area(PL, self.faceLeft), self.faceLeft) - self.pressureFlux(AfL, self.face)
        fixR = self.pressureFlux(self.area(PR, self.faceRight), self.faceRight) - self.pressureFlux(AfR, self.face)
        return fixL, fixR

    def faceFlux(self, PL, QL, PR, QR):
        """
        Flux at every face from the pressure and flow of the traces on its left and
        right, plus the corrections for the neighbouring cells.
        """
        UL = np.array([self.area(PL, self.face), QL])
        UR = np.array([self.area(PR, self.face), QR])
        fixL, fixR = self.corrections(PL, PR, UL[0], UR[0])
        return self.riemann(UL, UR, self.face), fixL, fixR

    def divergence(self, F, fixL, fixR):
        """(G_right - G_left)/dx for the interior cells, G being the face flux seen by the cell."""
        GR = F[:, 1:].copy()
        GL = F[:, :-1].copy()
        GR[1] += fixL[1:]
        GL[1] += fixR[:-1]
        return (GR - GL) / self.dx

    # --- time stepping -------------------------------------------------------

    def substeps(self, U):
        lam1, lam2 = self.eigenvalues(U, self.cell)
        courant = np.max(np.maximum(np.abs(lam1), np.abs(lam2))) * self.dt / self.dx
        nSub = max(1, int(np.ceil(courant / self.cflLimit)))
        return nSub, self.dt / nSub

    def __call__(self):
        n = self.currentMemoryIndex[0]
        self.n = n
        U = np.array([self.A[n], self.Q[n]], dtype=float)
        nSub, dt = self.substeps(U)
        for _ in range(nSub):
            U = self.step(U, dt)
        self.write(n, U[:, 1:-1])

    def write(self, n, Uinner):
        if not np.all(np.isfinite(Uinner)) or np.any(Uinner[0] <= 0):
            raise ValueError("{}: non-finite or non-positive area at step {}".format(self.name, n))
        self.A[n + 1][1:-1] = Uinner[0]
        self.Q[n + 1][1:-1] = Uinner[1]
        self.P[n + 1][1:-1] = self.pressure(Uinner[0], self.inner)
        if (self.P[n + 1][1:-1] < 0).any():
            raise ValueError("{}: negative pressure at step {}".format(self.name, n))

    def step(self, U, dt):
        raise NotImplementedError


def vanLeer(a, b):
    return np.where(a * b > 0.0, 2.0 * a * b / np.where(a + b == 0.0, 1.0, a + b), 0.0)


class LaxWendroff(ConservativeField):
    """Two-step Richtmyer Lax-Wendroff; the half step works on face-mapped states."""

    cflLimit = 0.9

    def halfStep(self, U, dt):
        P = self.pressure(U[0], self.cell)
        UL = np.array([self.area(P[:-1], self.face), U[1, :-1]])
        UR = np.array([self.area(P[1:], self.face), U[1, 1:]])
        Uh = 0.5 * (UL + UR) - 0.5 * dt / self.dx * (self.flux(UR, self.face) - self.flux(UL, self.face)) \
            + 0.25 * dt * (self.source(UL) + self.source(UR))
        Ph = self.pressure(Uh[0], self.face)
        fixL, fixR = self.corrections(Ph, Ph, Uh[0], Uh[0])
        Sh = self.source(Uh)
        return self.divergence(self.flux(Uh, self.face), fixL, fixR), 0.5 * (Sh[:, :-1] + Sh[:, 1:])

    def step(self, U, dt):
        div, S = self.halfStep(U, dt)
        Unew = U.copy()
        Unew[:, 1:-1] = U[:, 1:-1] - dt * div + dt * S
        return Unew


class TaylorGalerkin(LaxWendroff):
    """
    Two-step Taylor-Galerkin with linear elements between nodes. The predictor is
    the Lax-Wendroff half step at element midpoints; the corrector uses the
    consistent mass matrix, which is what separates it from Lax-Wendroff.
    """

    cflLimit = 0.55  # consistent mass: stable up to 1/sqrt(3)

    def setup(self):
        m = self.N - 2
        self.mass = np.zeros((3, m))
        self.mass[0, 1:] = 1.0 / 6.0
        self.mass[1, :] = 4.0 / 6.0
        self.mass[2, :-1] = 1.0 / 6.0

    def step(self, U, dt):
        div, S = self.halfStep(U, dt)
        rhs = -dt * div + dt * S
        Unew = U.copy()
        Unew[:, 1:-1] += solve_banded((1, 1), self.mass, rhs.T).T
        return Unew


class FV_MUSCL_HLL(ConservativeField):
    """Finite volume, MUSCL reconstruction of (P, Q) with van Leer limiter, SSP-RK2."""

    cflLimit = 0.9

    def rhs(self, U):
        W = np.array([self.pressure(U[0], self.cell), U[1]])
        slope = np.zeros_like(W)
        slope[:, 1:-1] = vanLeer(W[:, 1:-1] - W[:, :-2], W[:, 2:] - W[:, 1:-1])
        WL = W[:, :-1] + 0.5 * slope[:, :-1]
        WR = W[:, 1:] - 0.5 * slope[:, 1:]
        F, fixL, fixR = self.faceFlux(WL[0], WL[1], WR[0], WR[1])
        R = np.zeros_like(U)
        R[:, 1:-1] = -self.divergence(F, fixL, fixR) + self.source(U[:, 1:-1])
        return R

    def step(self, U, dt):
        U1 = U + dt * self.rhs(U)
        return 0.5 * U + 0.5 * (U1 + dt * self.rhs(U1))


class FV_MUSCL_Rusanov(FV_MUSCL_HLL):
    riemann = ConservativeField.rusanov


class MUSCL_Hancock(ConservativeField):
    """MUSCL-Hancock: limited slopes in (P, Q), half-step evolution of the cell traces, HLL flux."""

    cflLimit = 0.9

    def step(self, U, dt):
        dx, cell = self.dx, self.cell
        W = np.array([self.pressure(U[0], cell), U[1]])
        slope = np.zeros_like(W)
        slope[:, 1:-1] = vanLeer(W[:, 1:-1] - W[:, :-2], W[:, 2:] - W[:, 1:-1])
        WL, WR = W - 0.5 * slope, W + 0.5 * slope
        UL = np.array([self.area(WL[0], cell), WL[1]])
        UR = np.array([self.area(WR[0], cell), WR[1]])
        dF = self.flux(UL, cell) - self.flux(UR, cell)
        S = self.source(U)
        ULs = UL + 0.5 * dt / dx * dF + 0.5 * dt * S
        URs = UR + 0.5 * dt / dx * dF + 0.5 * dt * S
        for side in (0, -1):  # ghost cells are not evolved
            ULs[:, side] = URs[:, side] = U[:, side]
        PLs, PRs = self.pressure(ULs[0], cell), self.pressure(URs[0], cell)
        F, fixL, fixR = self.faceFlux(PRs[:-1], URs[1, :-1], PLs[1:], ULs[1, 1:])
        Uhalf = 0.5 * (ULs[:, 1:-1] + URs[:, 1:-1])
        Unew = U.copy()
        Unew[:, 1:-1] = U[:, 1:-1] - dt * self.divergence(F, fixL, fixR) + dt * self.source(Uhalf)
        return Unew


def lagrangeBasis(points):
    """Values at 0 and 1 and the derivative matrix D[g, j] = L_j'(x_g) for Lagrange polynomials on points."""
    m = len(points)

    def L(j, x):
        return np.prod([(x - points[k]) / (points[j] - points[k]) for k in range(m) if k != j], axis=0)

    def dL(j, x):
        total = 0.0
        for i in range(m):
            if i == j:
                continue
            term = 1.0 / (points[j] - points[i])
            for k in range(m):
                if k not in (i, j):
                    term = term * (x - points[k]) / (points[j] - points[k])
            total = total + term
        return total

    at0 = np.array([L(j, 0.0) for j in range(m)])
    at1 = np.array([L(j, 1.0) for j in range(m)])
    D = np.array([[dL(j, points[g]) for j in range(m)] for g in range(m)])
    return at0, at1, D


class ADER3(ConservativeField):
    """
    Third-order ADER finite volume scheme: CWENO3 reconstruction of (P, Q),
    a local space-time Galerkin predictor solved by Picard iteration, and
    time-integrated HLL fluxes at the faces.
    """

    cflLimit = 0.9
    order = 3
    picardIterations = 4

    def setup(self):
        m = self.order
        x, w = np.polynomial.legendre.leggauss(m)
        self.xg, self.wg = 0.5 * (x + 1.0), 0.5 * w           # Gauss points on [0, 1]
        at0, at1, D = lagrangeBasis(self.xg)
        self.psi0, self.psi1 = at0, at1
        W = np.diag(self.wg)
        F1 = np.kron(W, np.outer(at1, at1))                    # [theta_l theta_k] at tau = 1
        Ktau = np.kron(W, (D * self.wg[:, None]).T)            # int dtheta_l/dtau theta_k
        self.Kxi = np.kron(self.wg[:, None] * D, W)             # int theta_l dtheta_k/dxi
        self.Mst = np.kron(W, W)                                # space-time mass (diagonal)
        self.K1inv = np.linalg.inv(F1 - Ktau)
        self.F0 = np.kron(np.diag(self.wg), at0[:, None])       # maps w(x_a) to int theta_l(xi, 0) w
        self.innerNodes = {key: np.broadcast_to(value, (m * m, self.N - 2)) for key, value in self.inner.items()}

    def reconstruct(self, w):
        """CWENO3 polynomial w(xi) = w0 + w1 (xi - 1/2) + w2 ((xi - 1/2)^2 - 1/12) per interior cell."""
        um, u0, up = w[:-2], w[1:-1], w[2:]
        sL, sR = u0 - um, up - u0
        a1, a2 = 0.5 * (up - um), 0.5 * (up - 2.0 * u0 + um)
        cL, cR, c0 = 0.25, 0.25, 0.5
        isL, isR = sL ** 2, sR ** 2
        is0 = 13.0 / 3.0 * (2.0 * a2) ** 2 + 0.25 * (2.0 * a1) ** 2
        # relative to the variation along the vessel, with a floor for uniform states
        eps = (1e-2 * np.ptp(w) + 1e-8 * np.max(np.abs(w)) + 1e-30) ** 2
        aL, aR, a0 = cL / (eps + isL) ** 2, cR / (eps + isR) ** 2, c0 / (eps + is0) ** 2
        total = aL + aR + a0
        wL, wR, w0 = aL / total, aR / total, a0 / total
        lin = wL * sL + wR * sR + w0 * (a1 - cL * sL - cR * sR) / c0
        quad = w0 * a2 / c0
        xi = self.xg[:, None] - 0.5
        return u0[None, :] + lin[None, :] * xi + quad[None, :] * (xi ** 2 - 1.0 / 12.0)  # (m, ncell)

    def step(self, U, dt):
        m, dx = self.order, self.dx
        geo = self.innerNodes
        P = self.pressure(U[0], self.cell)
        Pg = self.reconstruct(P)
        Qg = self.reconstruct(U[1])
        w0 = np.array([self.area(Pg, self.inner), Qg])         # (2, m, nc)

        # space-time predictor with the cell's own tube law; nodes ordered a*m + b (a space, b time)
        rhs0 = np.einsum('la,vac->vlc', self.F0, w0)
        q = np.repeat(w0, m, axis=1)
        for _ in range(self.picardIterations):
            r = rhs0 - dt / dx * np.einsum('lk,vkc->vlc', self.Kxi, self.flux(q, geo)) \
                + dt * np.einsum('lk,vkc->vlc', self.Mst, self.source(q))
            q = np.einsum('lk,vkc->vlc', self.K1inv, r)

        qst = q.reshape(2, m, m, self.N - 2)
        right = np.einsum('a,vabc->vbc', self.psi1, qst)      # trace at xi = 1, per time node
        left = np.einsum('a,vabc->vbc', self.psi0, qst)       # trace at xi = 0

        # face traces (pressure, flow) over time; ghost cells keep their time-n state
        PL = np.empty((m, self.N - 1)); QL = np.empty((m, self.N - 1))
        PR = np.empty((m, self.N - 1)); QR = np.empty((m, self.N - 1))
        PL[:, 0], QL[:, 0] = P[0], U[1, 0]
        PL[:, 1:], QL[:, 1:] = self.pressure(right[0], self.inner), right[1]
        PR[:, -1], QR[:, -1] = P[-1], U[1, -1]
        PR[:, :-1], QR[:, :-1] = self.pressure(left[0], self.inner), left[1]
        Fbar, fixLbar, fixRbar = 0.0, 0.0, 0.0
        for b in range(m):
            F, fixL, fixR = self.faceFlux(PL[b], QL[b], PR[b], QR[b])
            Fbar = Fbar + self.wg[b] * F
            fixLbar = fixLbar + self.wg[b] * fixL
            fixRbar = fixRbar + self.wg[b] * fixR
        Sbar = np.einsum('k,vkc->vc', np.diag(self.Mst), self.source(q))

        Unew = U.copy()
        Unew[:, 1:-1] = U[:, 1:-1] - dt * self.divergence(Fbar, fixLbar, fixRbar) + dt * Sbar
        return Unew


class DG_P2(ConservativeField):
    """
    Modal discontinuous Galerkin with Legendre polynomials up to degree p on each
    interior cell, HLL interface fluxes and SSP-RK3 time stepping. The modal
    coefficients persist between steps; the solution arrays receive the point
    value at each cell centre.
    """

    degree = 2
    cflLimit = 0.18  # about 1/(2p+1) for SSP-RK3

    def setup(self):
        p = self.degree
        x, w = np.polynomial.legendre.leggauss(p + 2)
        self.xq, self.wq = x, w
        self.Vq = np.polynomial.legendre.legvander(x, p)        # P_k(x_q)
        self.dVq = np.stack([np.polynomial.legendre.legval(x, np.polynomial.legendre.legder(np.eye(p + 1)[k]))
                             for k in range(p + 1)], axis=1)
        self.right = np.ones(p + 1)                              # P_k(1)
        self.left = (-1.0) ** np.arange(p + 1)                   # P_k(-1)
        self.centre = np.polynomial.legendre.legvander(np.array([0.0]), p)[0]
        self.norm = 2.0 * np.arange(p + 1) + 1.0
        self.quadGeo = {key: np.broadcast_to(value, (p + 2, self.N - 2)) for key, value in self.inner.items()}
        self.coeffs = None
        self.lastOutput = None

    def project(self, U):
        """L2 projection of linear (P, Q) profiles through the nodes, with A from each cell's tube law."""
        P = self.pressure(U[0], self.cell)
        xi = self.xq[:, None]
        Pq = P[None, 1:-1] + 0.25 * (P[None, 2:] - P[None, :-2]) * xi
        Qq = U[1, None, 1:-1] + 0.25 * (U[1, None, 2:] - U[1, None, :-2]) * xi
        Uq = np.array([self.area(Pq, self.quadGeo), Qq])
        return 0.5 * self.norm[None, :, None] * np.einsum('q,qk,vqc->vkc', self.wq, self.Vq, Uq)

    def rhs(self, c, ghost):
        Uq = np.einsum('qk,vkc->vqc', self.Vq, c)
        volume = np.einsum('q,qk,vqc->vkc', self.wq, self.dVq, self.flux(Uq, self.quadGeo))
        src = np.einsum('q,qk,vqc->vkc', self.wq, self.Vq, self.source(Uq))

        trR = np.einsum('k,vkc->vc', self.right, c)
        trL = np.einsum('k,vkc->vc', self.left, c)
        PL = np.empty(self.N - 1); QL = np.empty(self.N - 1)
        PR = np.empty(self.N - 1); QR = np.empty(self.N - 1)
        PL[0], QL[0] = self.pressure(ghost[0, 0], self.faceLeft)[0], ghost[1, 0]
        PL[1:], QL[1:] = self.pressure(trR[0], self.inner), trR[1]
        PR[-1], QR[-1] = self.pressure(ghost[0, 1], self.faceRight)[-1], ghost[1, 1]
        PR[:-1], QR[:-1] = self.pressure(trL[0], self.inner), trL[1]
        F, fixL, fixR = self.faceFlux(PL, QL, PR, QR)
        GR = F[:, 1:].copy(); GR[1] += fixL[1:]
        GL = F[:, :-1].copy(); GL[1] += fixR[:-1]
        surface = GR[:, None, :] * self.right[None, :, None] - GL[:, None, :] * self.left[None, :, None]
        return (self.norm[None, :, None] / self.dx) * (volume - surface) + 0.5 * self.norm[None, :, None] * src

    def __call__(self):
        n = self.currentMemoryIndex[0]
        self.n = n
        U = np.array([self.A[n], self.Q[n]], dtype=float)
        if self.coeffs is None or self.lastOutput is None or \
                not np.allclose(self.lastOutput, U[:, 1:-1], rtol=1e-12, atol=0.0):
            self.coeffs = self.project(U)
        ghost = U[:, [0, -1]]
        nSub, dt = self.substeps(U)
        c = self.coeffs
        for _ in range(nSub):
            c1 = c + dt * self.rhs(c, ghost)
            c2 = 0.75 * c + 0.25 * (c1 + dt * self.rhs(c1, ghost))
            c = c / 3.0 + 2.0 / 3.0 * (c2 + dt * self.rhs(c2, ghost))
        self.coeffs = c
        Ucentre = np.einsum('k,vkc->vc', self.centre, c)
        self.write(n, Ucentre)
        self.lastOutput = Ucentre.copy()


schemes = {cls.__name__: cls for cls in (LaxWendroff, TaylorGalerkin, FV_MUSCL_HLL, FV_MUSCL_Rusanov,
                                          MUSCL_Hancock, ADER3, DG_P2)}
