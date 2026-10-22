"""Physical and actual-controller monitors for the SI 1D hemorrhage example."""

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import h5py
import numpy as np


def load_run(run):
    output=Path(run['hdf5']).parent
    dat=lambda kind,owner: np.loadtxt(output/f'netlist{kind}_{owner}.dat',ndmin=2)[:,1:]
    ph,qh,vh=(dat(kind,'surface_0') for kind in ('Pressures','Flows','Volumes'))
    beds=[(dat('Pressures',f'surface_{surface}'),dat('Flows',f'surface_{surface}')) for surface in (1,2)]
    pd,qd=(dat(kind,'downstreamCircuit_0') for kind in ('Pressures','Flows'))
    pb,qb=(dat(kind,'surface_3') for kind in ('Pressures','Flows'))
    trace=np.genfromtxt(output/'heart_controller_trace.csv',delimiter=',',names=True)
    source=Path(run['input'])
    vascular=ET.parse(source)
    xml=ET.parse(source.parent/'netlist_surfaces.xml')
    downstream=ET.parse(source.parent/'netlist_closed_loop_downstream.xml')
    with h5py.File(run['hdf5']) as data:
        time=data['VascularNetwork/simulationTime'][...]
        dt=float(data['VascularNetwork'].attrs['dt'])
        count=len(time)
        if len(trace)!=count or not np.array_equal(trace['step'],np.arange(count)):
            raise ValueError('actual controller and physical history sample counts differ')
        if ph.shape[0]!=count:
            raise ValueError('circuit and vessel sample counts differ')
        vessel_volume=np.zeros(count)
        vessel_net_flow=np.zeros(count)
        vessel_balance={}
        min_vessel_pressure=float('inf')
        min_vessel_area=float('inf')
        endpoint_errors={'pressure_pa':0.,'flow_m3_s':0.}
        endpoints_within_tolerance=True
        for group in data['vessels'].values():
            vessel_id=int(group.name.rsplit('-',1)[-1])
            # HDF group labels convention: Vessel - <id> (allow attribute fallback).
            node=vascular.find(f"./vessels/vessel[@Id='{vessel_id}']")
            if node is None:
                raise ValueError('cannot map HDF vessel group to input topology: '+group.name)
            if node.findtext('./geometry/geometryType')!='uniform':
                raise ValueError('this example volume ledger expects uniform vessels')
            length=float(node.findtext('./geometry/length'))
            area=group['Asol']
            volume=np.zeros(count)
            for start in range(0,count,8192):
                stop=min(count,start+8192)
                volume[start:stop]=np.trapezoid(area[start:stop],dx=length/(area.shape[1]-1),axis=1)
                min_vessel_area=min(min_vessel_area,float(np.min(area[start:stop])))
                min_vessel_pressure=min(min_vessel_pressure,float(np.min(group['Psol'][start:stop])))
            vessel_volume+=volume
            net_flow=group['Qsol'][:,0]-group['Qsol'][:,-1]
            vessel_net_flow+=net_flow
            local_defect=volume-volume[0]-np.r_[0.,dt*np.cumsum(net_flow[1:])]
            vessel_balance[str(vessel_id)]={'final_m3':float(local_defect[-1]),
                'max_abs_m3':float(np.max(np.abs(local_defect)))}
            for vid,position,pressure,flow,sign in ((1,0,ph[:,0],qh[:,0],-1),
                    (2,-1,beds[0][0][:,0],beds[0][1][:,0],1),
                    (4,-1,beds[1][0][:,0],beds[1][1][:,0],1),
                    (5,-1,pb[:,0],qb[:,0],1)):
                if vessel_id==vid:
                    vp,vq=group['Psol'][:,position],sign*group['Qsol'][:,position]
                    endpoint_errors['pressure_pa']=max(endpoint_errors['pressure_pa'],float(np.max(np.abs(vp-pressure))))
                    endpoint_errors['flow_m3_s']=max(endpoint_errors['flow_m3_s'],float(np.max(np.abs(vq-flow))))
                    endpoints_within_tolerance &= bool(np.allclose(vp,pressure,rtol=5e-11,atol=1e-8)
                                                       and np.allclose(vq,flow,rtol=5e-11,atol=1e-12))
    bed_storage=np.zeros(count)
    for circuit,(pressure,flow) in zip(xml.findall('./circuit')[1:3],beds):
        component=circuit.find("./components/component[type='capacitor']")
        capacitance=float(component.findtext('parameterValue'))
        start,end=int(component.findtext('startNodeIndex'))-1,int(component.findtext('endNodeIndex'))-1
        # The copied RCR capacitor points from reference into arterial storage.
        bed_storage+=capacitance*(pressure[:,end]-pressure[:,start])
    capacitance=float(downstream.findtext("./circuit/components/component[type='capacitor']/parameterValue"))
    return_storage=capacitance*(pd[:,1]-pd[:,3])
    signed_loss=np.r_[0.,dt*np.cumsum(qb[1:,0])]
    gross_loss=np.r_[0.,dt*np.cumsum(np.maximum(qb[1:,0],0.))]
    expected_controller_loss=np.r_[0.,dt*np.cumsum(np.maximum(qb[:-1,0],0.))]
    ledger=vessel_volume+vh[:,0]+bed_storage+return_storage
    defect=ledger-ledger[0]+signed_loss
    vessel_influx=np.r_[0.,dt*np.cumsum(vessel_net_flow[1:])]
    external_influx=np.r_[0.,dt*np.cumsum((-qh[1:,0]-beds[0][1][1:,0]
                                         -beds[1][1][1:,0]-qb[1:,0]))]
    vessel_defect=vessel_volume-vessel_volume[0]-vessel_influx
    junction_defect=vessel_influx-external_influx
    maxabs=lambda values:float(np.max(np.abs(values),initial=0.))
    checks={'endpoint_errors':endpoint_errors,
        'endpoints_within_tolerance':endpoints_within_tolerance,
        'min_vessel_pressure_pa':min_vessel_pressure,'min_vessel_area_m2':min_vessel_area,
        'max_shared_kcl_m3_s':max(maxabs(beds[0][1][:,2]+beds[1][1][:,2]-qd[:,0]),maxabs(qd[:,1]-qh[:,4])),
        'max_shared_pressure_pa':max(maxabs(beds[0][0][:,3]-pd[:,0]),maxabs(beds[1][0][:,3]-pd[:,0]),maxabs(ph[:,5]-pd[:,2])),
        'max_lv_volume_history_m3_s':maxabs(np.diff(vh[:,0])/dt-qh[1:,2]),
        'max_venous_capacitor_history_m3_s':maxabs(capacitance*np.diff(pd[:,1]-pd[:,3])/dt-qd[1:,2]),
        'max_controller_loss_recurrence_m3':maxabs(trace['controller_lost_volume_m3']-expected_controller_loss),
        'max_heart_rate_period_consistency_bpm':maxabs(trace['heart_rate_bpm']-60./trace['period_s']),
        'min_lv_volume_m3':float(np.min(vh[:,0])), 'min_aortic_pressure_pa':float(np.min(ph[:,0])),
        'min_bleed_flow_m3_s':float(np.min(qb[:,0])),
        'initial_storage_ledger_m3':float(ledger[0]), 'final_storage_ledger_m3':float(ledger[-1]),
        'final_net_lost_volume_m3':float(signed_loss[-1]), 'final_positive_lost_volume_m3':float(gross_loss[-1]),
        'final_controller_lost_volume_m3':float(trace['controller_lost_volume_m3'][-1]),
        'initial_heart_rate_bpm':float(trace['heart_rate_bpm'][0]),'final_heart_rate_bpm':float(trace['heart_rate_bpm'][-1]),
        'max_heart_rate_bpm':float(np.max(trace['heart_rate_bpm'])),
        'peak_aortic_ejection_flow_m3_s':float(np.max(-qh[:,0])),
        'peak_mitral_filling_flow_m3_s':float(np.max(qh[:,4])),
        'completed_controller_cycles':int(np.count_nonzero(np.diff(trace['phase_s'])<0)),
        'max_storage_plus_loss_defect_m3':maxabs(defect),'final_storage_plus_loss_defect_m3':float(defect[-1]),
        'vessel_volume_balance':vessel_balance,
        'final_vessel_continuity_defect_m3':float(vessel_defect[-1]),
        'final_junction_flow_integral_m3':float(junction_defect[-1]),
        'max_circuit_storage_balance_residual_m3':maxabs(defect-vessel_defect-junction_defect),
        'dt_s':dt,'accepted_steps':count-1,'final_time_s':float(time[-1])}
    signals={'time_s':time,'aortic_pressure_pa':ph[:,0],'lv_pressure_pa':ph[:,2],'venous_pressure_pa':pd[:,1],
        'aortic_flow_m3_s':-qh[:,0],'mitral_flow_m3_s':qh[:,4],'bleed_flow_m3_s':qb[:,0],
        'systemic_bed_1_flow_m3_s':beds[0][1][:,0],'systemic_bed_2_flow_m3_s':beds[1][1][:,0],
        'lv_volume_m3':vh[:,0],'vessel_volume_m3':vessel_volume,'systemic_compliance_storage_m3':bed_storage,
        'venous_compliance_storage_m3':return_storage,'storage_ledger_m3':ledger,
        'lost_volume_m3':signed_loss,'positive_lost_volume_m3':gross_loss,
        'controller_lost_volume_m3':trace['controller_lost_volume_m3'],'heart_rate_bpm':trace['heart_rate_bpm'],
        'heart_period_s':trace['period_s'],'elastance_pa_per_m3':trace['elastance_pa_per_m3'],
        'storage_plus_loss_defect_m3':defect,'vessel_continuity_defect_m3':vessel_defect,
        'junction_flow_integral_m3':junction_defect}
    np.savetxt(output/'heart_monitors.csv',np.column_stack(tuple(signals.values())),delimiter=',',
               header=','.join(signals),comments='',fmt='%.15g')
    return signals,checks


def plots(signals,folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for suffix,window in (('full',None),('last_beats',5.)):
        fig,axes=plt.subplots(3,2,figsize=(13,10),sharex=True,constrained_layout=True)
        definitions=(('Pressure','mmHg',(('aortic_pressure_pa','Aortic',1/133.322),('lv_pressure_pa','LV',1/133.322))),
            ('Flow','mL/s',(('aortic_flow_m3_s','Aortic',1e6),('bleed_flow_m3_s','Bleed',1e6))),
            ('LV chamber volume','mL',(('lv_volume_m3','LV',1e6),)),
            ('Actual feedback controller heart rate','bpm',(('heart_rate_bpm','HR',1.),)),
            ('Cumulative external blood loss','mL',(('lost_volume_m3','Physical loss',1e6),('controller_lost_volume_m3','Controller integral',1e6))),
            ('Storage + lost-volume balance defect','mL',(('storage_plus_loss_defect_m3','Discrete ledger defect',1e6),)))
        for ax,(title,unit,fields) in zip(axes.flat,definitions):
            for field,label,scale in fields:
                for backend,style in (('cpp','-'),('python','--')):
                    row=signals[backend]
                    mask=np.ones(len(row['time_s']),dtype=bool) if window is None else row['time_s']>=row['time_s'][-1]-window
                    ax.plot(row['time_s'][mask],scale*row[field][mask],style,lw=1.1,label=label+' '+backend)
            ax.set_title(title);ax.set_ylabel(unit);ax.grid(alpha=.2);ax.legend(fontsize=8)
        axes[-1,0].set_xlabel('Time (s)');axes[-1,1].set_xlabel('Time (s)')
        fig.suptitle('1D closed-loop heart with external hemorrhage: C++ and NumPy')
        for extension in ('png','pdf'):
            fig.savefig(folder/f'heart_{suffix}.{extension}',dpi=160)
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,5),constrained_layout=True)
    for backend,style in (('cpp','-'),('python','--')):
        row=signals[backend];mask=row['time_s']>=max(0.,row['time_s'][-1]-5.)
        ax.plot(row['lv_volume_m3'][mask]*1e6,row['lv_pressure_pa'][mask]/133.322,style,lw=1.,label=backend)
    ax.set(xlabel='LV volume (mL)',ylabel='LV pressure (mmHg)',title='Actual final 5 seconds: LV pressure-volume trajectory')
    ax.legend();ax.grid(alpha=.2)
    for extension in ('png','pdf'):
        fig.savefig(folder/f'pressure_volume.{extension}',dpi=160)
    plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True,constrained_layout=True)
    for backend,style in (('cpp','-'),('python','--')):
        row=signals[backend];time=row['time_s']
        axes[0].plot(time,row['storage_ledger_m3']*1e6,style,label='Tracked storage '+backend)
        axes[0].plot(time,(row['storage_ledger_m3']+row['lost_volume_m3'])*1e6,style,
                     label='Storage + external loss '+backend)
        for field,label in (('vessel_volume_m3','1D vessels'),('lv_volume_m3','LV'),
                ('systemic_compliance_storage_m3','Systemic compliance'),
                ('venous_compliance_storage_m3','Venous compliance')):
            axes[1].plot(time,row[field]*1e6,style,label=label+' '+backend)
    axes[0].set_title('Tracked storage and external loss; initial storage is the conservation reference')
    axes[1].set_title('Storage components; compliance volumes are relative to fixed pressure references')
    for ax in axes:
        ax.set_ylabel('mL');ax.legend(fontsize=8,ncol=2);ax.grid(alpha=.2)
    axes[-1].set_xlabel('Time (s)')
    for extension in ('png','pdf'):
        fig.savefig(folder/f'storage_components.{extension}',dpi=160)
    plt.close(fig)


def analyze(comparison,folder):
    signals,diagnostics={},{}
    for backend in ('cpp','python'):
        signals[backend],diagnostics[backend]=load_run(comparison[backend])
    accuracy={}
    for field in signals['cpp']:
        old,new=signals['cpp'][field],signals['python'][field]
        if old.shape!=new.shape:
            raise ValueError('monitor sample counts differ: '+field)
        atol=1e-8 if 'pressure_pa' in field or 'rate_bpm' in field else 1e-5 if 'elastance' in field else 1e-12
        difference=np.abs(new-old)
        accuracy[field]={'max_abs':float(np.max(difference,initial=0.)),
            'rmse':float(np.sqrt(np.mean(difference*difference))),
            'rtol':5e-11,'atol':atol,'passed':bool(np.all(difference<=atol+5e-11*np.abs(old)))}
    physical_checks={backend: bool(
        check['max_shared_kcl_m3_s']<=1e-12 and check['max_shared_pressure_pa']<=1e-8
        and check['max_lv_volume_history_m3_s']<=1e-12 and check['max_venous_capacitor_history_m3_s']<=1e-12
        and check['max_controller_loss_recurrence_m3']<=1e-12
        and check['max_heart_rate_period_consistency_bpm']<=1e-8
        and check['min_lv_volume_m3']>=0 and check['min_vessel_pressure_pa']>=0
        and check['min_vessel_area_m2']>0 and check['endpoints_within_tolerance']
        and (check['final_time_s']<3. or (check['peak_aortic_ejection_flow_m3_s']>1e-8
                                        and check['completed_controller_cycles']>=2)))
        for backend,check in diagnostics.items()}
    result={'passed':all(row['passed'] for row in accuracy.values()) and all(physical_checks.values()),
        'accuracy':accuracy,'physical_checks_passed':physical_checks,'diagnostics':diagnostics,
        'volume_ledger':'V_vessels + V_LV + sum(C_systemic*(P_internal-P_reference)) + C_venous*(P_reservoir-P_reference)',
        'loss_convention':'physical loss = dt*sum(q_bleed accepted n+1); controller integral uses positive prior-published q at iter_init; both are recorded',
        'conservation_note':'storage+loss defect includes existing 1D discretization error; reported independently of algebraic KCL and backend agreement'}
    (folder/'heart_validation.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    plots(signals,folder)
    strict_passed=result['passed'] and comparison['accuracy']['passed']
    lines=['# 1D closed-loop blood-loss heart', '',
        'Both simulations completed. Strict comparison status: **'+('passed' if strict_passed else 'failed tolerance')+'**.', '',
        'This runs the original tutorial 1D vessel tree, valved LV heart and SI blood-loss feedback law.',
        'The two systemic RCR beds now return blood through the source closed-loop example’s venous R/R/C',
        'circuit. The bleeding outlet remains an external drain and is not joined to the venous return.',
        'There is no generated 0D replacement of the vessels and no prescribed inflow waveform.', '',
        'Both backends use the same simultaneous 1D characteristics and pre-solve controller lifecycle.',
        'C++ runs native circuit equations and Python-2 controllers; NumPy calls reference kernels in process.', '',
        '| Quantity | C++ | NumPy |', '| --- | ---: | ---: |']
    for label,key,scale in (('Accepted steps','accepted_steps',1),('Final time (s)','final_time_s',1),
            ('Initial HR (bpm)','initial_heart_rate_bpm',1),('Final HR (bpm)','final_heart_rate_bpm',1),
            ('Final external lost volume (mL)','final_net_lost_volume_m3',1e6),
            ('Final controller-integrated loss (mL)','final_controller_lost_volume_m3',1e6),
            ('Minimum LV volume (mL)','min_lv_volume_m3',1e6),
            ('Peak aortic ejection (mL/s)','peak_aortic_ejection_flow_m3_s',1e6),
            ('Completed feedback cycles','completed_controller_cycles',1),
            ('Max storage + loss balance defect (mL)','max_storage_plus_loss_defect_m3',1e6)):
        lines.append('| {} | {:.10g} | {:.10g} |'.format(label,diagnostics['cpp'][key]*scale,diagnostics['python'][key]*scale))
    lines+=['| Solver wall time (s) | {:.6f} | {:.6f} |'.format(comparison['cpp']['solve_seconds'],comparison['python']['solve_seconds']),
        '', 'Observed NumPy speedup: {:.3f}x. Single sequential run per backend; timings include the complete 1D solve and native IPC.'.format(
            comparison['cpp']['solve_seconds']/comparison['python']['solve_seconds']), '',
        '## Validation interpretation', '',
        'Local circuit/lifecycle/endpoint checks: C++ **{}**, NumPy **{}**.'.format(
            'passed' if physical_checks['cpp'] else 'failed','passed' if physical_checks['python'] else 'failed'),
        'The strict tolerances are retained. Long-run differences above those thresholds are reported as failures.',
        'The monitor checks exceeding tolerance are: '+(', '.join(name for name,row in accuracy.items() if not row['passed']) or 'none')+'.',
        'All per-dataset failures, including internal circuit pressures, remain in `comparison.json`.', '',
        'The final storage-plus-loss defect is {:.6f} mL ({:.3f}% of initial tracked storage) in C++.'.format(
            diagnostics['cpp']['final_storage_plus_loss_defect_m3']*1e6,
            abs(diagnostics['cpp']['final_storage_plus_loss_defect_m3'])/diagnostics['cpp']['initial_storage_ledger_m3']*100),
        'Its decomposition is {:.6f} mL from vessel volume continuity and {:.6f} mL from integrated internal junction flow imbalance.'.format(
            diagnostics['cpp']['final_vessel_continuity_defect_m3']*1e6,
            diagnostics['cpp']['final_junction_flow_integral_m3']*1e6),
        'The remaining circuit-storage balance residual is at most {:.6g} mL.'.format(
            diagnostics['cpp']['max_circuit_storage_balance_residual_m3']*1e6),
        'This volume defect requires a conservation investigation before treating the case as quantitatively validated.', '',
        '## Tracked signals', '',
        'Each backend’s `SolutionData_001/heart_monitors.csv` contains pressure, flow, LV volume,',
        'vessel volume, compliance storage, actual heart rate/period/elastance, physical lost volume,',
        'controller-integrated loss and the storage-plus-loss defect at every saved timestep.',
        '`heart_controller_trace.csv` records actual backend controller state; it is not reconstructed',
        'from the other solver. C++ logs its own class state; NumPy logs accepted controller state.', '',
        'The controller reads previous published bleed flow before each solve. Its integral therefore',
        'differs from accepted-endpoint backward-Euler physical loss by one endpoint sample.', '',
        '![Full trajectory](heart_full.png)', '', '![Final five seconds](heart_last_beats.png)', '',
        '![LV pressure-volume trajectory](pressure_volume.png)', '',
        '![Tracked volume components and blood loss](storage_components.png)', '',
        '## Accuracy', '', '| Monitor | Max absolute NumPy − C++ difference |', '| --- | ---: |']
    for field,row in accuracy.items():
        lines.append('| {} | {:.6g} |'.format(field,row['max_abs']))
    lines+=['', '[Full vessel/circuit accuracy and timings](comparison.md). ',
        '[Numerical checks and volume ledger](heart_validation.json). PNG and PDF figures are both saved.', '',
        'The ledger includes vessel quadrature plus LV and compliant storage relative to fixed pressure',
        'references. Its changes are meaningful; this is not an independently calibrated total blood volume.',
        'Its balance defect measures existing 1D discretization as well as coupling. It is not hidden',
        'by the much smaller algebraic KCL or C++/NumPy differences.', '',
        'This is a numerical demonstration using tutorial parameters, not a calibrated physiological model.', '']
    (folder/'heart_report.md').write_text('\n'.join(lines))
    return result
