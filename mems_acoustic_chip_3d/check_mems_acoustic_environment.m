function status = check_mems_acoustic_environment()
%CHECK_MEMS_ACOUSTIC_ENVIRONMENT Check MATLAB and COMSOL LiveLink access.

import com.comsol.model.util.*

status = struct( ...
    'matlab_version', version, ...
    'mphstart_path', which('mphstart'), ...
    'mphsave_path', which('mphsave'), ...
    'mphglobal_path', which('mphglobal'), ...
    'comsol_version', '', ...
    'ready', false);

try
    status.comsol_version = char(ModelUtil.getComsolVersion);
    status.ready = true;
catch err
    status.error = err.message;
end
disp(status);
end
