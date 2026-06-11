function status = check_matlab_comsol_environment()
%CHECK_MATLAB_COMSOL_ENVIRONMENT Check MATLAB and COMSOL LiveLink access.

status = struct( ...
    'matlab_version', version, ...
    'mphstart_path', which('mphstart'), ...
    'mphsave_path', which('mphsave'), ...
    'comsol_version', '', ...
    'ready', false);

try
    import com.comsol.model.util.*
    status.comsol_version = char(ModelUtil.getComsolVersion);
    status.ready = true;
catch err
    status.error = err.message;
end

disp(status);
end
