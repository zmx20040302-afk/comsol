function model = run_3d_bulb_diagnostic()
%RUN_3D_BULB_DIAGNOSTIC Check LiveLink, log output, then build the model.

folder = fileparts(mfilename('fullpath'));
log_file = fullfile(folder, 'build_3d_bulb_log.txt');

if exist(log_file, 'file')
    delete(log_file);
end
diary(log_file);
cleanup = onCleanup(@() diary('off')); %#ok<NASGU>

fprintf('=== 3D bulb COMSOL diagnostic ===\n');
fprintf('MATLAB version: %s\n', version);
fprintf('Working folder: %s\n', pwd);
fprintf('Diagnostic file: %s\n', mfilename('fullpath'));

builder = which('build_electrochemical_polishing_3d_bulb');
expected_builder = fullfile(folder, 'build_electrochemical_polishing_3d_bulb.m');
fprintf('Resolved builder: %s\n', builder);
fprintf('Expected builder: %s\n', expected_builder);
if ~strcmpi(builder, expected_builder)
    error(['MATLAB is not using the expected builder file. Run clear functions, ' ...
        'rehash, and verify the current folder.']);
end

fprintf('mphstart path: %s\n', which('mphstart'));
fprintf('mphopen path: %s\n', which('mphopen'));

try
    import com.comsol.model.util.*
    comsol_version = char(ModelUtil.getComsolVersion);
    fprintf('COMSOL connection ready. Version: %s\n', comsol_version);
catch err
    fprintf(2, '\nCOMSOL LiveLink connection is not ready.\n');
    fprintf(2, ['Start MATLAB from the COMSOL installation shortcut named ' ...
        '"COMSOL with MATLAB", or connect to a running COMSOL server with mphstart.\n']);
    fprintf(2, '%s\n', getReport(err, 'extended', 'hyperlinks', 'off'));
    rethrow(err);
end

model = build_electrochemical_polishing_3d_bulb;
fprintf('Diagnostic build completed successfully.\n');
fprintf('Log file: %s\n', log_file);
end
