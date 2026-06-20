import numpy as np


def solve_robin_characteristic(position, omega_known, R, P, Q, dp_dq, hop, flow_sign=1.0):
    """
    Solve the local 1D characteristic boundary equation with a netlist-style
    affine pressure-flow relation:

        P_new = dp_dq * (flow_sign * Q_new) + hop

    Parameters
    ----------
    position : int
        STARFiSh boundary position. `0` is proximal, `-1` is distal.
    omega_known : float
        Characteristic increment provided by the vessel interior.
    R : ndarray, shape (2, 2)
        Characteristic-to-[dP, dQ] transform.
    P, Q : float
        Current boundary pressure and flow before applying the boundary update.
    dp_dq, hop : float
        Netlist affine coefficients.
    flow_sign : float
        Sign mapping from STARFiSh flow to netlist interface flow.

    Returns
    -------
    omega : ndarray, shape (2,)
        Characteristic increment vector ordered for `np.dot(R, omega)`.
    """
    r11, r12 = R[0][0], R[0][1]
    r21, r22 = R[1][0], R[1][1]
    signed_slope = dp_dq * flow_sign

    if position == -1:
        denominator = r12 - signed_slope * r22
        numerator = signed_slope * Q + hop - P + (signed_slope * r21 - r11) * omega_known
        omega = np.empty(2)
        omega[0] = omega_known
        omega[1] = numerator / denominator
        return omega

    if position == 0:
        denominator = r11 - signed_slope * r21
        numerator = signed_slope * Q + hop - P + (signed_slope * r22 - r12) * omega_known
        omega = np.empty(2)
        omega[0] = numerator / denominator
        omega[1] = omega_known
        return omega

    raise ValueError("Unsupported boundary position for netlist coupling: {}".format(position))


def solve_prescribed_flow_characteristic(position, omega_known, R, Q, prescribed_flow=0.0):
    """
    Solve the local characteristic system when CRIMSON reports that no flow is
    permitted across the netlist interface.

    The closed-interface condition is:

        Q_new = prescribed_flow

    For diode-blocked netlists the prescribed flow is currently zero.
    """
    r21, r22 = R[1][0], R[1][1]

    if position == -1:
        omega = np.empty(2)
        omega[0] = omega_known
        omega[1] = (prescribed_flow - Q - r21 * omega_known) / r22
        return omega

    if position == 0:
        omega = np.empty(2)
        omega[0] = (prescribed_flow - Q - r22 * omega_known) / r21
        omega[1] = omega_known
        return omega

    raise ValueError("Unsupported boundary position for netlist coupling: {}".format(position))


class NetlistBoundaryInterface(object):
    """
    Interface layer between STARFiSh Type 2 boundary calls and the netlist
    coefficient source.
    """

    def __init__(self, surface_id, position, flow_sign, manager):
        self.surface_id = int(surface_id)
        self.position = position
        self.flow_sign = float(flow_sign)
        self.manager = manager

    def solve(self, omega_known, R, nmem, n, dt, P, Q, A, Z1, Z2):
        time = (n + 1) * dt
        flow_permitted, boundary_type_changed, dp_dq, hop = (
            self.manager.compute_interface_data(
                self.surface_id,
                n,
                time,
                dt,
                P,
                self.flow_sign * Q,
            )
        )
        del boundary_type_changed
        if not flow_permitted:
            omega = solve_prescribed_flow_characteristic(
                self.position,
                omega_known,
                R,
                Q,
                prescribed_flow=0.0,
            )
            du = np.dot(R, omega)
            self.manager.record_boundary_state(
                self.surface_id,
                timestep=n,
                time=time,
                dt=dt,
                pressure=P + du[0],
                flow=self.flow_sign * (Q + du[1]),
            )
            if self.position == -1:
                dQInOut = (R[:][1] * omega)[::-1].copy()
            else:
                dQInOut = R[:][1] * omega
            return du, dQInOut
        omega = solve_robin_characteristic(
            self.position,
            omega_known,
            R,
            P,
            Q,
            dp_dq,
            hop,
            flow_sign=self.flow_sign,
        )
        du = np.dot(R, omega)
        self.manager.record_boundary_state(
            self.surface_id,
            timestep=n,
            time=time,
            dt=dt,
            pressure=P + du[0],
            flow=self.flow_sign * (Q + du[1]),
        )

        if self.position == -1:
            dQInOut = (R[:][1] * omega)[::-1].copy()
        else:
            dQInOut = R[:][1] * omega
        return du, dQInOut
