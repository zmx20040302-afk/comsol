function model = build_electrochemical_polishing_3d_bulb()
%BUILD_ELECTROCHEMICAL_POLISHING_3D_BULB Build a grounded 3D COMSOL model.
%
% Run in COMSOL with MATLAB / LiveLink for MATLAB:
%   model = build_electrochemical_polishing_3d_bulb;
%
% Evidence mapping:
%   - Bulb-like geometry follows the light-bulb geometry example concept.
%   - Electric-current and moving-boundary settings follow the 2D
%     electrochemical-polishing example.
%   - 3D selections are coordinate/named selections. Verify them before use.

import com.comsol.model.*
import com.comsol.model.util.*

stage = 'initialization';
try
fprintf('[1/7] Initializing model and parameters...\n');
fprintf('Builder file: %s\n', mfilename('fullpath'));
fprintf('COMSOL version: %s\n', char(ModelUtil.getComsolVersion));
model = ModelUtil.create('Model');
model.label('electrochemical_polishing_3d_bulb.mph');

% Grounded values inherited from the 2D electrochemical-polishing example.
model.param.set('K', '1e-11[m^3/(A*s)]', ...
    'Depletion coefficient from the 2D reference');
model.param.set('V_applied', '30[V]', ...
    'Applied potential from the 2D reference');
model.param.set('sigma_el', '10[S/m]', ...
    'Conductivity from the 2D reference');
model.param.set('epsilonr_el', '80', ...
    'Relative permittivity from the 2D reference');

% New 3D geometry parameters. These are explicit design choices, not values
% inferred from the 2D electrochemical-polishing example.
model.param.set('R_bulb', '20[mm]', 'Bulb sphere radius');
model.param.set('z_bulb', '25[mm]', 'Bulb sphere center height');
model.param.set('R_neck', '8[mm]', 'Bulb neck radius');
model.param.set('z_neck', '-15[mm]', 'Bulb neck bottom');
% The neck must overlap the sphere. Point contact creates invalid/nonmanifold
% geometry in a 3D union.
model.param.set('H_neck', '25[mm]', 'Bulb neck height with sphere overlap');
model.param.set('selection_tol', '0.1[mm]', 'Selection tolerance');

stage = '3D geometry union';
fprintf('[2/7] Building overlapping sphere-cylinder geometry...\n');
model.component.create('comp1', true);
model.component('comp1').geom.create('geom1', 3);
model.component('comp1').geom('geom1').lengthUnit('mm');

model.component('comp1').geom('geom1').create('sph1', 'Sphere');
model.component('comp1').geom('geom1').feature('sph1').label('Bulb');
model.component('comp1').geom('geom1').feature('sph1').set('r', 'R_bulb');
model.component('comp1').geom('geom1').feature('sph1').set('pos', ...
    {'0' '0' 'z_bulb'});
model.component('comp1').geom('geom1').feature('sph1').set('selresult', true);

model.component('comp1').geom('geom1').create('cyl1', 'Cylinder');
model.component('comp1').geom('geom1').feature('cyl1').label('Neck');
model.component('comp1').geom('geom1').feature('cyl1').set('r', 'R_neck');
model.component('comp1').geom('geom1').feature('cyl1').set('h', 'H_neck');
model.component('comp1').geom('geom1').feature('cyl1').set('pos', ...
    {'0' '0' 'z_neck'});
model.component('comp1').geom('geom1').feature('cyl1').set('selresult', true);

model.component('comp1').geom('geom1').create('uni1', 'Union');
model.component('comp1').geom('geom1').feature('uni1').selection('input').set( ...
    {'sph1' 'cyl1'});
model.component('comp1').geom('geom1').feature('uni1').set('intbnd', false);
model.component('comp1').geom('geom1').run;

% Selection names replace fragile 2D numeric boundary IDs.
stage = '3D named selections';
fprintf('[3/7] Creating coordinate and generated selections...\n');
model.component('comp1').selection.create('sel_ground', 'Box');
model.component('comp1').selection('sel_ground').label('Ground bottom');
model.component('comp1').selection('sel_ground').set('entitydim', 2);
model.component('comp1').selection('sel_ground').set('zmax', ...
    'z_neck+selection_tol');
model.component('comp1').selection('sel_ground').set('condition', 'inside');

model.component('comp1').selection.create('sel_fixed', 'Box');
model.component('comp1').selection('sel_fixed').label('Fixed neck boundaries');
model.component('comp1').selection('sel_fixed').set('entitydim', 2);
model.component('comp1').selection('sel_fixed').set('zmax', ...
    'z_neck+H_neck-selection_tol');
model.component('comp1').selection('sel_fixed').set('condition', 'inside');

% The sphere feature's resulting boundary selection is the moving electrode.
% Inspect this named selection after geometry changes.
moving_selection = 'geom1_sph1_bnd';

stage = 'electric currents and deformed geometry';
fprintf('[4/7] Adding electric-current and moving-boundary constraints...\n');
model.component('comp1').variable.create('var1');
model.component('comp1').variable('var1').set('dx', 'x-Xg');
model.component('comp1').variable('var1').set('dy', 'y-Yg');
model.component('comp1').variable('var1').set('dz', 'z-Zg');

model.component('comp1').physics.create('ec', 'ConductiveMedia', 'geom1');
model.component('comp1').physics('ec').prop('EquationForm').setIndex( ...
    'form', 'Stationary', 0);
model.component('comp1').physics('ec').feature('cucns1').set( ...
    'sigma_mat', 'userdef');
model.component('comp1').physics('ec').feature('cucns1').set( ...
    'sigma', {'sigma_el' '0' '0' '0' 'sigma_el' '0' '0' '0' 'sigma_el'});
model.component('comp1').physics('ec').feature('cucns1').set( ...
    'epsilonr_mat', 'userdef');
model.component('comp1').physics('ec').feature('cucns1').set( ...
    'epsilonr', {'epsilonr_el' '0' '0' '0' 'epsilonr_el' '0' '0' '0' 'epsilonr_el'});

model.component('comp1').physics('ec').create('pot1', 'ElectricPotential', 2);
model.component('comp1').physics('ec').feature('pot1').selection.named( ...
    moving_selection);
model.component('comp1').physics('ec').feature('pot1').set('V0', 'V_applied');

model.component('comp1').physics('ec').create('gnd1', 'Ground', 2);
model.component('comp1').physics('ec').feature('gnd1').selection.named( ...
    'sel_ground');

model.component('comp1').common.create( ...
    'free1', 'DeformingDomainDeformedGeometry');
model.component('comp1').common('free1').selection.all;
model.component('comp1').common('free1').set('smoothingType', 'laplace');

model.component('comp1').common.create( ...
    'pnmv1', 'PrescribedNormalMeshVelocityDeformedGeometry');
model.component('comp1').common('pnmv1').selection.named(moving_selection);
model.component('comp1').common('pnmv1').set( ...
    'prescribedNormalVelocity', '-K*(-ec.nJ)');

model.component('comp1').common.create( ...
    'pnmd1', 'PrescribedNormalMeshDisplacementDeformedGeometry');
model.component('comp1').common('pnmd1').selection.named('sel_fixed');

stage = 'tetrahedral mesh';
fprintf('[5/7] Building tetrahedral mesh...\n');
model.component('comp1').mesh.create('mesh1');
model.component('comp1').mesh('mesh1').autoMeshSize(3);
model.component('comp1').mesh('mesh1').create('ftet1', 'FreeTet');
model.component('comp1').mesh('mesh1').run;

stage = 'transient study and selection validation';
fprintf('[6/7] Creating study and validating selections...\n');
model.study.create('std1');
model.study('std1').create('time', 'Transient');
model.study('std1').feature('time').set('tlist', 'range(0,10)');
model.study('std1').createAutoSequences('all');

% Stop before solving if a generated 3D selection is empty.
assert_nonempty_selection(model, moving_selection, 'moving bulb boundary');
assert_nonempty_selection(model, 'sel_ground', 'ground boundary');
assert_nonempty_selection(model, 'sel_fixed', 'fixed neck boundaries');

stage = 'transient solve and results';
fprintf('[7/7] Solving and saving results...\n');
model.study('std1').run;

model.result.create('pg_current', 'PlotGroup3D');
model.result('pg_current').label('Current Density and Deformed Bulb');
model.result('pg_current').create('surf1', 'Surface');
model.result('pg_current').feature('surf1').set('expr', 'ec.normJ');

model.result.create('pg_displacement', 'PlotGroup3D');
model.result('pg_displacement').label('Z Displacement');
model.result('pg_displacement').create('surf1', 'Surface');
model.result('pg_displacement').feature('surf1').set('expr', 'dz');

output_file = fullfile(fileparts(mfilename('fullpath')), ...
    'electrochemical_polishing_3d_bulb.mph');
model.save(output_file);
fprintf('Saved: %s\n', output_file);
catch err
    fprintf(2, '\nBuild failed during stage: %s\n', stage);
    fprintf(2, 'COMSOL/MATLAB message: %s\n', err.message);
    fprintf(2, '%s\n', getReport(err, 'extended', 'hyperlinks', 'off'));
    if exist('model', 'var')
        debug_file = fullfile(fileparts(mfilename('fullpath')), ...
            'electrochemical_polishing_3d_bulb_failed_stage.mph');
        try
            model.save(debug_file);
            fprintf(2, 'Partial model saved for inspection: %s\n', debug_file);
        catch
        end
    end
    rethrow(err);
end
end


function assert_nonempty_selection(model, tag, description)
entities = mphgetselection(model.component('comp1').selection(tag));
if isempty(entities.entities)
    error('Selection "%s" (%s) is empty. Inspect the 3D geometry before solving.', ...
        tag, description);
end
fprintf('Selection %-18s: %d entities (%s)\n', ...
    tag, numel(entities.entities), description);
end
