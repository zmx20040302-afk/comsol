function model = build_mems_acoustic_chip_3d()
%BUILD_MEMS_ACOUSTIC_CHIP_3D Build and solve a grounded 3D MEMS acoustic test.
%
% The solved component is a rigid-wall rectangular air cavity. A second,
% unsolved component shows the silicon substrate and membrane geometry.
% No unsupported piezoelectric, thermoviscous, damping, or acoustic-
% structure coupling settings are assumed.

import com.comsol.model.*
import com.comsol.model.util.*

model = ModelUtil.create('Model');
model.label('mems_acoustic_chip_3d.mph');
model.title('3D MEMS Acoustic Chip - Rigid Cavity Verification');

model.param.set('Lchip', '3[mm]', 'Chip length');
model.param.set('Wchip', '2.5[mm]', 'Chip width');
model.param.set('Tsub', '300[um]', 'Silicon substrate thickness');
model.param.set('Lx', '2[mm]', 'Acoustic cavity length');
model.param.set('Ly', '1.5[mm]', 'Acoustic cavity width');
model.param.set('Hcav', '0.5[mm]', 'Acoustic cavity height');
model.param.set('Tmem', '10[um]', 'Membrane display thickness');
model.param.set('c_air', '343[m/s]', 'Speed of sound in air');
model.param.set('rho_air', '1.225[kg/m^3]', 'Air density');
model.param.set('f_shift', '80[kHz]', 'Eigenfrequency search shift');
model.param.set('fmax_test', '400[kHz]', 'Maximum verified frequency');
model.param.set('hmax', 'c_air/(6*fmax_test)', 'Six elements per wavelength');
model.param.set('f100_ref', 'c_air/(2*Lx)', 'Analytical mode (1,0,0)');
model.param.set('f010_ref', 'c_air/(2*Ly)', 'Analytical mode (0,1,0)');
model.param.set('f110_ref', ...
    'c_air/2*sqrt((1/Lx)^2+(1/Ly)^2)', 'Analytical mode (1,1,0)');
model.param.set('f200_ref', 'c_air/Lx', 'Analytical mode (2,0,0)');
model.param.set('f001_ref', 'c_air/(2*Hcav)', 'Analytical mode (0,0,1)');

% Solved acoustic air cavity.
model.component.create('acoustic', true);
model.component('acoustic').label('Acoustic Test Cavity');
model.component('acoustic').geom.create('geom1', 3);
model.component('acoustic').geom('geom1').lengthUnit('m');
model.component('acoustic').geom('geom1').create('air1', 'Block');
model.component('acoustic').geom('geom1').feature('air1').label('Sealed Air Cavity');
model.component('acoustic').geom('geom1').feature('air1').set('size', {'Lx' 'Ly' 'Hcav'});
model.component('acoustic').geom('geom1').feature('air1').set( ...
    'pos', {'-Lx/2' '-Ly/2' 'Tsub'});
model.component('acoustic').geom('geom1').run;

model.component('acoustic').material.create('air', 'Common');
model.component('acoustic').material('air').label('Air');
model.component('acoustic').material('air').propertyGroup('def').set('density', 'rho_air');
model.component('acoustic').material('air').propertyGroup('def').set('soundspeed', 'c_air');

% Pressure Acoustics supplies the default Sound Hard wall condition.
model.component('acoustic').physics.create('acpr', 'PressureAcoustics', 'geom1');

model.component('acoustic').mesh.create('mesh1');
model.component('acoustic').mesh('mesh1').create('size1', 'Size');
model.component('acoustic').mesh('mesh1').feature('size1').set('custom', true);
model.component('acoustic').mesh('mesh1').feature('size1').set('hmax', 'hmax');
model.component('acoustic').mesh('mesh1').create('ftet1', 'FreeTet');
model.component('acoustic').mesh('mesh1').run;

% Display-only chip geometry. It deliberately has no physics assigned.
model.component.create('chip', true);
model.component('chip').label('MEMS Chip Geometry - Display Only');
model.component('chip').geom.create('geom2', 3);
model.component('chip').geom('geom2').lengthUnit('m');
model.component('chip').geom('geom2').create('sub1', 'Block');
model.component('chip').geom('geom2').feature('sub1').label('Silicon Substrate');
model.component('chip').geom('geom2').feature('sub1').set('size', {'Lchip' 'Wchip' 'Tsub'});
model.component('chip').geom('geom2').feature('sub1').set( ...
    'pos', {'-Lchip/2' '-Wchip/2' '0'});
model.component('chip').geom('geom2').create('mem1', 'Block');
model.component('chip').geom('geom2').feature('mem1').label('MEMS Membrane');
model.component('chip').geom('geom2').feature('mem1').set('size', {'Lx' 'Ly' 'Tmem'});
model.component('chip').geom('geom2').feature('mem1').set( ...
    'pos', {'-Lx/2' '-Ly/2' 'Tsub+Hcav'});
model.component('chip').geom('geom2').run;

model.study.create('std1');
model.study('std1').label('3D Acoustic Eigenfrequency Test');
model.study('std1').create('eig', 'Eigenfrequency');
model.study('std1').feature('eig').set('neigs', 12);
model.study('std1').feature('eig').set('shift', 'f_shift');
model.study('std1').createAutoSequences('all');
model.study('std1').run;

model.result.create('pg_pressure', 'PlotGroup3D');
model.result('pg_pressure').label('3D Acoustic Pressure Eigenmode');
model.result('pg_pressure').set('data', 'dset1');
model.result('pg_pressure').create('slc1', 'Slice');
model.result('pg_pressure').feature('slc1').set('expr', 'real(acoustic.p)');
model.result('pg_pressure').feature('slc1').set('descr', 'Real acoustic pressure');
model.result('pg_pressure').run;

model.result.create('pg_spl', 'PlotGroup3D');
model.result('pg_spl').label('3D Sound Pressure Level Eigenmode');
model.result('pg_spl').set('data', 'dset1');
model.result('pg_spl').create('slc1', 'Slice');
model.result('pg_spl').feature('slc1').set('expr', 'acoustic.acpr.Lp_t');
model.result('pg_spl').feature('slc1').set('descr', 'Sound pressure level');
model.result('pg_spl').run;

mphsave(model, fullfile(pwd, 'mems_acoustic_chip_3d.mph'));
fprintf('Saved: %s\n', fullfile(pwd, 'mems_acoustic_chip_3d.mph'));
end
